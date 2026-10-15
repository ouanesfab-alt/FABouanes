"""
Responsibility: Consolidated Database Engine and Migration Orchestration.
Canonical point of entry for database connections, engines, migrations, sessions, and Unit of Work.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from contextlib import contextmanager
from decimal import Decimal
import functools
import importlib
import logging
import os
from pathlib import Path
import re
import sys
import threading
from threading import RLock
from time import monotonic
from typing import Any, Callable
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine

from werkzeug.security import generate_password_hash

from app.core.config import APP_DATA_DIR, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME, settings
from app.infra.perf_cache import invalidate_cache_domains
from app.core.request_state import ensure_request_state, get_request_state
from app.core.runtime_paths import ensure_runtime_dirs

# Async DB & Unit of Work canonical re-exports
from app.core.async_db import (  # noqa: F401
    AsyncSessionLocal,
    async_healthcheck,
    close_async_engine,
    create_db_and_tables,
    execute_sql_async,
    get_async_database_url,
    get_async_engine,
    get_async_session,
    get_async_sessionmaker,
    query_sql_async,
)
from app.core.base_repository import AsyncRepository, BaseRepository  # noqa: F401
from app.core.uow import unit_of_work, with_uow  # noqa: F401

logger = logging.getLogger("fabouanes")
_PERF_LOGGER = logging.getLogger("fabouanes.performance")

_BOOTSTRAP_LOCK = RLock()
_BOOTSTRAPPED = False


def is_sqlite() -> bool:
    """Return True if the configured DATABASE_URL is SQLite."""
    from app.core.config import DATABASE_URL
    return "sqlite" in (DATABASE_URL or "").lower()



# ---------------------------------------------------------------------------
# Low-level DB compatibility objects
# ---------------------------------------------------------------------------

class CompatRow(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values_tuple = tuple(self.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values_tuple[key]
        return super().__getitem__(key)


def _wrap_rows(rows, description):
    if not description:
        return rows
    cols = [c[0] for c in description]
    wrapped = []
    for row in rows:
        wrapped.append(CompatRow(OrderedDict(zip(cols, row))))
    return wrapped


class CompatCursor:
    def __init__(self, cursor, description=None):
        self.cursor = cursor
        self.description = description or getattr(cursor, "description", None)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return _wrap_rows(rows, self.description)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return _wrap_rows([row], self.description)[0]

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def lastrowid(self):
        return getattr(self.cursor, "lastrowid", None)


def _clean_params(params):
    if not params:
        return params
    if not isinstance(params, (tuple, list)):
        if isinstance(params, dict):
            return {k: (Decimal(str(v)) if isinstance(v, float) else v) for k, v in params.items()}
        return params
    cleaned = []
    for p in params:
        if isinstance(p, float):
            cleaned.append(Decimal(str(p)))
        elif isinstance(p, list):
            cleaned.append([Decimal(str(x)) if isinstance(x, float) else x for x in p])
        elif isinstance(p, tuple):
            cleaned.append(tuple(Decimal(str(x)) if isinstance(x, float) else x for x in p))
        else:
            cleaned.append(p)
    return tuple(cleaned) if isinstance(params, tuple) else cleaned


class CompatConnection:
    def __init__(
        self,
        conn,
        dialect: str = "postgres",
        on_close: Callable[[Any], None] | None = None,
        reconnect: Callable[[], Any] | None = None,
    ):
        self.conn = conn
        self.dialect = "postgres"
        self._on_close = on_close
        self._reconnect = reconnect
        self._closed = False

    def execute(self, query: str, params: tuple = ()):
        if not isinstance(query, str):
            query = str(query)
        retried = False
        cleaned_params = _clean_params(params)
        while True:
            cur = self.conn.cursor()
            try:
                cur.execute(query, cleaned_params)
                return CompatCursor(cur)
            except Exception as exc:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

                exc_msg = str(exc).lower()
                if ("25p02" in exc_msg or "transaction is aborted" in exc_msg) and not retried:
                    retried = True
                    continue

                if not retried:
                    from sqlalchemy.exc import DBAPIError, OperationalError

                    if isinstance(exc, (OperationalError, DBAPIError)) or "connection" in exc_msg:
                        self._reset_postgres_connection()
                        retried = True
                        continue
                raise

    def executescript(self, script: str):
        for statement in split_sql_script(script):
            if statement.strip():
                self.execute(statement)
        return None

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._on_close is not None:
            self._on_close(self.conn)
            return
        self.conn.close()

    def _reset_postgres_connection(self) -> None:
        if self._reconnect is None:
            raise RuntimeError("Connexion PostgreSQL perdue et reconnexion indisponible.")
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = self._reconnect()


# ---------------------------------------------------------------------------
# SQL Script & Validation Utilities
# ---------------------------------------------------------------------------

def split_sql_script(script: str) -> list[str]:
    statements = []
    current = []
    in_dollar = False
    in_single_quote = False
    in_double_quote = False

    i = 0
    n = len(script)
    while i < n:
        char = script[i]

        if not in_dollar and not in_single_quote and not in_double_quote:
            if char == "-" and i + 1 < n and script[i + 1] == "-":
                i += 2
                while i < n and script[i] != "\n":
                    i += 1
                continue
            if char == "/" and i + 1 < n and script[i + 1] == "*":
                i += 2
                while i < n and not (script[i] == "*" and i + 1 < n and script[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        if char == "$" and i + 1 < n and script[i + 1] == "$":
            in_dollar = not in_dollar
            current.append("$$")
            i += 2
            continue

        if not in_dollar:
            if char == "'" and (i == 0 or script[i - 1] != "\\"):
                in_single_quote = not in_single_quote
            elif char == '"' and (i == 0 or script[i - 1] != "\\"):
                in_double_quote = not in_double_quote

        if char == ";" and not in_dollar and not in_single_quote and not in_double_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def validate_identifier(name: str) -> None:
    if not name or not isinstance(name, str):
        raise ValueError("Invalid database identifier")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\.]*$", name):
        raise ValueError(f"Invalid database identifier: {name}")


# ---------------------------------------------------------------------------
# DatabaseManager: Connection Pooling & Synchronous Execution
# ---------------------------------------------------------------------------

class DatabaseManager:
    MAX_UNPAGINATED_ROWS = 10_000

    def __init__(self):
        self._slow_sql_threshold_ms = float(os.environ.get("FAB_SLOW_SQL_MS", "100") or "100")
        self._perf_queue_maxlen = int(os.environ.get("FAB_PERF_QUEUE_MAXLEN", "1000") or "1000")
        self._perf_queue = deque(maxlen=max(100, self._perf_queue_maxlen))
        self._perf_lock = threading.Lock()
        self._perf_event = threading.Event()
        self._perf_worker_started = False
        self._perf_worker_lock = threading.Lock()
        self._perf_conn = None
        self._perf_conn_lock = threading.Lock()
        self._perf_shutdown = False

        self._engines: dict[str, Engine] = {}
        self._engine_lock = threading.Lock()

    def _env_int(self, name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
        try:
            value = int(os.environ.get(name, str(default)) or default)
        except Exception:
            value = default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def sqlalchemy_database_url(self, database_url: str) -> str:
        url = str(database_url or "").strip()
        if url.startswith("postgresql://"):
            return "postgresql+pg8000://" + url[len("postgresql://") :]
        if url.startswith("postgres://"):
            return "postgresql+pg8000://" + url[len("postgres://") :]
        return url

    def create_database_engine(self, database_url: str) -> Engine:
        engine_url = self.sqlalchemy_database_url(database_url)
        is_sqlite = "sqlite" in str(engine_url).lower()
        if is_sqlite:
            engine = create_engine(
                engine_url,
                future=True,
                pool_pre_ping=True,
                connect_args={"timeout": 30.0},
            )
        else:
            is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")
            sync_default_pool = 1 if is_termux else 2
            pool_size = self._env_int("FAB_SYNC_PG_POOL_SIZE", self._env_int("FAB_PG_POOL_SIZE", sync_default_pool, 1, 50), 1, 50)
            max_overflow = self._env_int("FAB_SYNC_PG_MAX_OVERFLOW", 3, 0, 50)
            engine = create_engine(
                engine_url,
                future=True,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=self._env_int("FAB_PG_POOL_TIMEOUT", 30, 1, 300),
                pool_recycle=self._env_int("FAB_PG_POOL_RECYCLE_SECONDS", 1800, 60, 86400),
            )

        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_connection_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                if is_sqlite:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA busy_timeout=10000")
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                else:
                    cursor.execute("SET TIME ZONE 'UTC'")
            except Exception:
                pass
            finally:
                cursor.close()

        try:
            from app.core.observability import instrument_sqlalchemy

            instrument_sqlalchemy(engine)
        except Exception:
            pass
        return engine

    def get_database_engine(self, database_url: str) -> Engine:
        raw_url = str(database_url or "").strip()
        with self._engine_lock:
            engine = self._engines.get(raw_url)
            if engine is None:
                engine = self.create_database_engine(raw_url)
                self._engines[raw_url] = engine
            return engine

    def connect_database(self, database_url: str) -> CompatConnection:
        raw_url = str(database_url or "").strip()
        for attempt in range(2):
            try:
                engine = self.get_database_engine(raw_url)
                try:
                    conn = engine.raw_connection()
                    timeout_ms = int(os.environ.get("FAB_PG_STATEMENT_TIMEOUT_MS", "30000") or "30000")
                    cursor = conn.cursor()
                    try:
                        cursor.execute(f"SET statement_timeout = {timeout_ms}")
                    finally:
                        cursor.close()
                    return CompatConnection(
                        conn,
                        reconnect=lambda: self.connect_database(raw_url),
                    )
                except Exception as conn_exc:
                    err_str = str(conn_exc).lower()
                    with self._engine_lock:
                        old_engine = self._engines.pop(raw_url, None)
                        if old_engine is not None:
                            try:
                                old_engine.dispose()
                            except Exception as dispose_exc:
                                logger.debug("Failed to dispose engine: %s", dispose_exc)

                    if "shut down" in err_str or "closed" in err_str or "could not connect" in err_str:
                        if attempt == 0:
                            try:
                                is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists(
                                    "/data/data/com.termux"
                                )
                                if is_termux:
                                    import subprocess

                                    subprocess.run(
                                        [
                                            "pg_ctl",
                                            "-D",
                                            f"{os.environ.get('PREFIX', '')}/var/lib/postgresql",
                                            "-o",
                                            "-c listen_addresses='*' -c port=5432",
                                            "start",
                                        ],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        check=False,
                                    )
                            except Exception:
                                pass
                            continue
                    raise conn_exc
            except Exception as e:
                err_msg = str(e).lower()
                if "does not exist" in err_msg or "3d000" in err_msg:
                    parsed = urlparse(raw_url)
                    database = parsed.path.lstrip("/")
                    port_part = f":{parsed.port}" if parsed.port else ""
                    pass_part = f":{parsed.password}" if parsed.password else ""
                    user_part = f"{parsed.username}{pass_part}@" if parsed.username else ""
                    postgres_url = f"{parsed.scheme}://{user_part}{parsed.hostname}{port_part}/postgres"

                    pg_engine = create_engine(
                        self.sqlalchemy_database_url(postgres_url),
                        future=True,
                        isolation_level="AUTOCOMMIT",
                    )
                    with pg_engine.connect() as admin_conn:
                        admin_conn.execute(text(f'CREATE DATABASE "{database}"'))
                    pg_engine.dispose()
                    with self._engine_lock:
                        self._engines.pop(raw_url, None)
                    return self.get_database_engine(raw_url).raw_connection()
                elif "authentification" in err_msg or "password authentication failed" in err_msg or "28p01" in err_msg:
                    raise RuntimeError(
                        "Erreur critique d'authentification PostgreSQL. Verifie le mot de passe dans .env"
                    ) from e
                elif attempt == 1:
                    raise RuntimeError(f"Impossible de se connecter a la base de donnees PostgreSQL: {e}") from e

        def _reconnect():
            return engine.raw_connection()

        return CompatConnection(
            conn,
            dialect="postgres",
            on_close=lambda c: c.close(),
            reconnect=_reconnect,
        )

    def postgres_pool_status(self, database_url: str) -> dict[str, int | str]:
        pool = self.get_database_engine(database_url).pool
        status: dict[str, int | str] = {"engine": "postgres"}
        for key, method_name in (
            ("size", "size"),
            ("checkedin", "checkedin"),
            ("checkedout", "checkedout"),
            ("overflow", "overflow"),
        ):
            method = getattr(pool, method_name, None)
            if callable(method):
                try:
                    status[key] = int(method())
                except Exception:
                    pass
        return status

    def get_db(self) -> CompatConnection:
        return self.get_write_db()

    def get_write_db(self) -> CompatConnection:
        state = get_request_state()
        if state is not None and getattr(state, "db", None) is not None:
            if not getattr(state.db, "_closed", False):
                return state.db
        state = ensure_request_state()
        if getattr(state, "db", None) is None or getattr(state.db, "_closed", False):
            state.db = self.connect_database(settings.database_url)
        return state.db

    def get_read_db(self) -> CompatConnection:
        if self._tx_depth() > 0:
            return self.get_write_db()
        read_url = os.environ.get("DATABASE_READ_URL", "").strip()
        if not read_url:
            return self.get_write_db()
        state = get_request_state()
        if state is not None and getattr(state, "read_db", None) is not None:
            if not getattr(state.read_db, "_closed", False):
                return state.read_db
        state = ensure_request_state()
        if getattr(state, "read_db", None) is None or getattr(state.read_db, "_closed", False):
            state.read_db = self.connect_database(read_url)
        return state.read_db

    def _tx_depth(self) -> int:
        state = get_request_state()
        if state is not None:
            return int(getattr(state, "db_tx_depth", 0) or 0)
        return 0

    def _set_tx_depth(self, value: int) -> None:
        state = ensure_request_state()
        state.db_tx_depth = value

    def _route_label(self) -> str:
        state = get_request_state()
        state_request = getattr(state, "request", None) if state is not None else None
        if state_request is None:
            return ""
        route = state_request.scope.get("route")
        endpoint = getattr(route, "name", "") or state_request.scope.get("endpoint_name", "")
        path = state_request.url.path
        return f"{state_request.method} {path}" if not endpoint else f"{state_request.method} {path} ({endpoint})"

    def _record_performance_event(self, kind: str, name: str, elapsed_ms: float, details: str = "") -> None:
        if "performance_logs" in name.lower() or elapsed_ms <= 0:
            return
        normalized_kind = kind if kind in ("sql", "route", "maintenance") else "route"
        event = (normalized_kind[:40], name[:240], float(elapsed_ms), self._route_label()[:300], details[:1000])
        with self._perf_lock:
            self._perf_queue.append(event)
        _PERF_LOGGER.warning("%s %.2fms %s %s", normalized_kind, elapsed_ms, name[:240], details[:200])
        self._ensure_performance_worker()
        self._perf_event.set()

    def _record_sql_timing(self, query: str, params: tuple, elapsed_ms: float) -> None:
        if elapsed_ms < self._slow_sql_threshold_ms:
            return
        normalized = " ".join(str(query or "").split())
        self._record_performance_event("sql", normalized, elapsed_ms, f"params={len(params or ())}")

    def _invalidate_after_write(self, query: str) -> None:
        q = f" {str(query or '').lower()} "
        if not any(token in q for token in (" insert ", " update ", " delete ", " replace ")):
            return
        domains: set[str] = set()
        if any(table in q for table in (" clients", " sales", " raw_sales", " payments")):
            domains.update({"clients", "client_detail", "dashboard", "payments", "sales", "transactions", "contacts"})
        if any(table in q for table in (" raw_materials", " finished_products")):
            domains.update({"catalog", "dashboard", "sales", "purchases", "productions", "transactions"})
        if " purchases" in q or " suppliers" in q:
            domains.update({"purchases", "transactions", "contacts", "dashboard"})
        if " production_batches" in q or " production_batch_items" in q:
            domains.update({"productions", "dashboard", "sales", "catalog"})
        if " expenses" in q:
            domains.update({"dashboard"})
        if any(
            table in q
            for table in (" users", " backup_jobs", " audit_logs", " activity_logs", " system_logs", " error_logs")
        ):
            domains.add("admin")
        if domains:
            invalidate_cache_domains(*domains)

    def _guard_pagination(self, query: str) -> str:
        q = query.strip().lower()
        if not q.startswith("select") and not q.startswith("("):
            return query
        if "count(*)" in q or "count(1)" in q:
            return query
        try:
            import sqlglot
            from sqlglot import exp

            parsed = sqlglot.parse_one(query, read="postgres")
            if isinstance(parsed, (exp.Select, exp.Union)):
                if not parsed.args.get("limit"):
                    logger.debug("[PAGINATION GUARD] Auto-LIMIT %d via sqlglot applique.", self.MAX_UNPAGINATED_ROWS)
                    return parsed.limit(self.MAX_UNPAGINATED_ROWS).sql(dialect="postgres")
        except Exception as exc:
            logger.warning("[PAGINATION GUARD] Fallback sur erreur de parsing sqlglot: %s", exc)

        if any(kw in q for kw in ("limit ", "limit\n", "for update", "for share")):
            return query
        logger.debug("[PAGINATION GUARD] Auto-LIMIT %d applique a: %s", self.MAX_UNPAGINATED_ROWS, query[:120])
        return f"{query.rstrip().rstrip(';')} LIMIT {self.MAX_UNPAGINATED_ROWS}"

    def query_db(self, query: str, params: tuple = (), one: bool = False):
        if not one:
            query = self._guard_pagination(query)
        started = monotonic()
        for attempt in range(2):
            db = self.get_read_db()
            try:
                cur = db.execute(query, params)
                if one:
                    result = cur.fetchone()
                else:
                    result = cur.fetchall()
                cur.close()
                self._record_sql_timing(query, params, (monotonic() - started) * 1000.0)
                return result
            except Exception as exc:
                exc_msg = str(exc).lower()
                is_transient = "connection" in exc_msg or "57p01" in exc_msg or "08006" in exc_msg or "08001" in exc_msg
                if self._tx_depth() == 0:
                    try:
                        db.rollback()
                    except Exception as e2:
                        logger.debug("Ignored error: %s", e2, exc_info=False)
                if is_transient and attempt == 0 and self._tx_depth() == 0:
                    logger.warning("Transient DB error on query_db (attempt %d), retrying: %s", attempt + 1, exc)
                    state = get_request_state()
                    if state is not None and getattr(state, "read_db", None) is not None:
                        try:
                            state.read_db.close()
                        except Exception:
                            pass
                        state.read_db = None
                    continue
                raise

    async def query_db_async(self, query: str, params: tuple = (), one: bool = False):
        return await asyncio.to_thread(self.query_db, query, params, one)

    def execute_db(self, query: str, params: tuple = ()) -> int:
        for attempt in range(2):
            db = self.get_write_db()
            started = monotonic()
            has_returning = bool(re.search(r"\breturning\b", query, flags=re.I))
            try:
                cur = db.execute(query, params)
                last_id = None
                if has_returning:
                    try:
                        row = cur.fetchone()
                        last_id = row[0] if row else None
                    except Exception:
                        logger.debug("Could not fetch RETURNING result", exc_info=True)
                else:
                    last_id = cur.lastrowid
                if self._tx_depth() == 0:
                    db.commit()
                cur.close()
            except Exception as exc:
                exc_msg = str(exc).lower()
                is_transient = "connection" in exc_msg or "57p01" in exc_msg or "08006" in exc_msg or "08001" in exc_msg
                if self._tx_depth() == 0:
                    try:
                        db.rollback()
                    except Exception as e2:
                        logger.debug("Ignored error: %s", e2, exc_info=False)
                if is_transient and attempt == 0 and self._tx_depth() == 0:
                    logger.warning("Transient DB error on execute_db (attempt %d), retrying: %s", attempt + 1, exc)
                    state = get_request_state()
                    if state is not None and getattr(state, "db", None) is not None:
                        try:
                            state.db.close()
                        except Exception:
                            pass
                        state.db = None
                    continue
                raise
            else:
                if not last_id:
                    last_id = self._postgres_last_insert_id(db, query)
                self._record_sql_timing(query, params, (monotonic() - started) * 1000.0)
                self._invalidate_after_write(query)
                return int(last_id or 0)
        return 0

    async def execute_db_async(self, query: str, params: tuple = ()) -> int:
        return await asyncio.to_thread(self.execute_db, query, params)

    def _postgres_last_insert_id(self, db, query: str) -> int:
        match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", str(query or ""), flags=re.I)
        if not match:
            return 0
        table = match.group(1)
        if table in {"app_settings", "schema_migrations", "idempotent_requests", "client_keys", "rate_limit_events"}:
            return 0
        try:
            cur = db.execute("SELECT currval(pg_get_serial_sequence(%s, 'id')) AS id", (table,))
            row = cur.fetchone()
            cur.close()
            return int(row["id"] if row else 0)
        except Exception as e:
            logger.debug("Ignored error: %s", e, exc_info=False)
            return 0

    def explain_query_plan(self, query: str, params: tuple = ()) -> list[dict]:
        db = self.get_db()
        prefix = "EXPLAIN "
        cur = db.execute(prefix + query, params)
        try:
            rows = cur.fetchall()
            return [dict(row) if hasattr(row, "keys") else {"plan": str(row)} for row in rows]
        finally:
            cur.close()

    @contextmanager
    def db_transaction(self):
        db = self.get_write_db()
        previous_depth = self._tx_depth()
        self._set_tx_depth(previous_depth + 1)
        savepoint_name = f"sp_depth_{previous_depth}"
        if previous_depth > 0:
            cur = db.execute(f"SAVEPOINT {savepoint_name}")
            cur.close()
        try:
            yield db
        except Exception:
            if previous_depth > 0:
                try:
                    cur = db.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    cur.close()
                except Exception as e2:
                    logger.debug("Ignored savepoint rollback error: %s", e2, exc_info=False)
            else:
                try:
                    db.rollback()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
            raise
        else:
            if previous_depth > 0:
                try:
                    cur = db.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    cur.close()
                except Exception as e2:
                    logger.debug("Ignored savepoint release error: %s", e2, exc_info=False)
            else:
                db.commit()
        finally:
            self._set_tx_depth(previous_depth)

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            row = self.query_db("SELECT value FROM app_settings WHERE key = %s", (key,), one=True)
            return row["value"] if row and row["value"] is not None else default
        except Exception as e:
            logger.debug("Ignored error: %s", e, exc_info=False)
            return default

    def set_setting(self, key: str, value: str) -> None:
        self.execute_db(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, value),
        )

    def list_columns(self, conn: CompatConnection, table: str) -> set[str]:
        cur = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        rows = cur.fetchall()
        cur.close()
        return {row["column_name"] for row in rows}

    def _ensure_performance_worker(self) -> None:
        if os.environ.get("FAB_DISABLE_PERFORMANCE_DB_LOGS", "0").strip() == "1":
            return
        if self._perf_worker_started:
            return
        with self._perf_worker_lock:
            if self._perf_worker_started:
                return
            thread = threading.Thread(target=self._performance_worker, name="fab-performance-log-writer", daemon=True)
            thread.start()
            self._perf_worker_started = True

    def _pop_performance_batch(self, limit: int = 50) -> list[tuple[str, str, float, str, str]]:
        batch: list[tuple[str, str, float, str, str]] = []
        with self._perf_lock:
            while self._perf_queue and len(batch) < limit:
                batch.append(self._perf_queue.popleft())
        return batch

    def _write_performance_batch(self, batch: list[tuple[str, str, float, str, str]]) -> None:
        if not batch:
            return
        with self._perf_conn_lock:
            now = monotonic()
            if self._perf_conn is not None:
                age = now - getattr(self, "_perf_conn_created_at", 0)
                if age > 900:
                    try:
                        self._perf_conn.close()
                    except Exception:
                        pass
                    self._perf_conn = None
            if self._perf_conn is None:
                self._perf_conn = self.connect_database(settings.database_url)
                self._perf_conn_created_at = now
            try:
                for kind, name, elapsed_ms, route, details in batch:
                    cur = self._perf_conn.execute(
                        """
                        INSERT INTO performance_logs (kind, name, elapsed_ms, route, details, created_at)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        """,
                        (kind, name, elapsed_ms, route, details),
                    )
                    cur.close()
                self._perf_conn.commit()
            except Exception as e:
                logger.warning("Echec de l'ecriture du lot de logs de performance: %s", e)
                try:
                    self._perf_conn.close()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
                self._perf_conn = None
                raise

    def _performance_worker(self) -> None:
        while not self._perf_shutdown:
            self._perf_event.wait(timeout=2.0)
            self._perf_event.clear()
            if self._perf_shutdown:
                break
            while True:
                batch = self._pop_performance_batch()
                if not batch:
                    break
                try:
                    self._write_performance_batch(batch)
                except Exception:
                    _PERF_LOGGER.exception("Unable to persist performance log batch")

    def shutdown(self) -> None:
        self._perf_shutdown = True
        self._perf_event.set()
        try:
            while True:
                batch = self._pop_performance_batch(limit=100)
                if not batch:
                    break
                self._write_performance_batch(batch)
        except Exception as e:
            logger.warning("Error draining performance logs: %s", e)
        with self._perf_conn_lock:
            if self._perf_conn is not None:
                try:
                    self._perf_conn.close()
                except Exception:
                    pass
                self._perf_conn = None

    def pending_performance_event_count(self) -> int:
        with self._perf_lock:
            return len(self._perf_queue)

    def drain_performance_events_once(self) -> int:
        batch = self._pop_performance_batch(500)
        self._write_performance_batch(batch)
        return len(batch)


# Global DatabaseManager singleton
db_manager = DatabaseManager()
ConnectionPoolManager = DatabaseManager
pool_manager = db_manager


# ---------------------------------------------------------------------------
# High-Level Helper Functions (DB API)
# ---------------------------------------------------------------------------

def sqlalchemy_database_url(database_url: str) -> str:
    return db_manager.sqlalchemy_database_url(database_url)


def create_database_engine(database_url: str) -> Engine:
    return db_manager.create_database_engine(database_url)


def get_database_engine(database_url: str) -> Engine:
    return db_manager.get_database_engine(database_url)


def connect_database(database_url: str) -> CompatConnection:
    return db_manager.connect_database(database_url)


def postgres_pool_status(database_url: str) -> dict[str, int | str]:
    return db_manager.postgres_pool_status(database_url)


def get_db() -> CompatConnection:
    return db_manager.get_db()


def get_write_db() -> CompatConnection:
    return db_manager.get_write_db()


def get_read_db() -> CompatConnection:
    return db_manager.get_read_db()


def query_db(query: str, params: tuple = (), one: bool = False):
    return db_manager.query_db(query, params, one)


async def query_db_async(query: str, params: tuple = (), one: bool = False):
    return await db_manager.query_db_async(query, params, one)


def execute_db(query: str, params: tuple = ()) -> int:
    return db_manager.execute_db(query, params)


async def execute_db_async(query: str, params: tuple = ()) -> int:
    return await db_manager.execute_db_async(query, params)


def explain_query_plan(query: str, params: tuple = ()) -> list[dict]:
    return db_manager.explain_query_plan(query, params)


def query_sa(query, one: bool = False):
    compiled = query.compile(dialect=postgresql.dialect(paramstyle="format"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in compiled.positiontup)
    return query_db(sql, params, one=one)


def execute_sa(query) -> int:
    compiled = query.compile(dialect=postgresql.dialect(paramstyle="format"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in compiled.positiontup)
    return execute_db(sql, params)


def list_columns(conn: CompatConnection, table: str) -> set[str]:
    return db_manager.list_columns(conn, table)


def pending_performance_event_count() -> int:
    return db_manager.pending_performance_event_count()


def drain_performance_events_once() -> int:
    return db_manager.drain_performance_events_once()


def db_task(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    wrapper.async_ = async_wrapper
    wrapper.sync = func
    return wrapper


@contextmanager
def db_transaction():
    with db_manager.db_transaction() as tx:
        yield tx


def get_setting(key: str, default: str = "") -> str:
    return db_manager.get_setting(key, default)


def set_setting(key: str, value: str) -> None:
    db_manager.set_setting(key, value)


update_setting = set_setting


# ---------------------------------------------------------------------------
# Alembic Migration Engine
# ---------------------------------------------------------------------------

def _load_alembic():
    if getattr(sys, "frozen", False):
        command = importlib.import_module("alembic.command")
        config_mod = importlib.import_module("alembic.config")
        return command, config_mod.Config

    original_sys_path = list(sys.path)
    base_dir = str(settings.base_dir.resolve())
    try:
        sys.path = [entry for entry in sys.path if str(Path(entry).resolve()) != base_dir]
        command = importlib.import_module("alembic.command")
        config_mod = importlib.import_module("alembic.config")
        return command, config_mod.Config
    finally:
        sys.path = original_sys_path


def _alembic_script_location() -> Path:
    bundled_location = settings.base_dir / "migration_scripts" / "alembic"
    if bundled_location.exists():
        return bundled_location
    return settings.base_dir / "alembic"


def _alembic_config():
    _, Config = _load_alembic()
    cfg = Config(str(settings.base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(_alembic_script_location()))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_database_url(settings.database_url))
    return cfg


def _alembic_version_exists() -> bool:
    engine = get_database_engine(settings.database_url)
    try:
        return inspect(engine).has_table("alembic_version")
    except Exception:
        return False


def run_alembic_upgrade() -> None:
    """Runs Alembic migrations up to head, with legacy revision self-healing."""
    if not (settings.base_dir / "alembic.ini").exists():
        return
    command, _ = _load_alembic()
    cfg = _alembic_config()
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        err_msg = str(exc)
        if "Can't locate revision" in err_msg or "Can't find revision" in err_msg:
            logger.warning("Legacy Alembic revision detected in database, resetting alembic_version: %s", exc)
            try:
                engine = get_database_engine(settings.database_url)
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM alembic_version"))
                    conn.commit()
                command.stamp(cfg, "head")
                logger.info("Successfully stamped Alembic version to head.")
                return
            except Exception as stamp_exc:
                logger.error("Failed to auto-stamp Alembic head: %s", stamp_exc)
        logger.warning("Alembic migration warning: %s", exc)


# ---------------------------------------------------------------------------
# Schema Seeding & Startup Bootstrap
# ---------------------------------------------------------------------------

FIRST_ADMIN_PASSWORD_FILE = APP_DATA_DIR / "first_admin_password.txt"
OTHER_OPERATION_NAME = "AUTRE"
OTHER_OPERATION_UNIT = "unite"


def initial_admin_password() -> str:
    configured = str(DEFAULT_ADMIN_PASSWORD or "").strip()
    allow_insecure = os.environ.get("FAB_ALLOW_INSECURE_DEFAULT_ADMIN", "0").strip() == "1"
    if configured and (configured != "1234" or allow_insecure):
        return configured
    if FIRST_ADMIN_PASSWORD_FILE.exists():
        try:
            for line in FIRST_ADMIN_PASSWORD_FILE.read_text(encoding="utf-8").splitlines():
                if line.startswith("PIN="):
                    value = line.split("=", 1)[1].strip()
                    if value:
                        return value
        except Exception:
            pass
    pin = "7508"
    ensure_runtime_dirs()
    FIRST_ADMIN_PASSWORD_FILE.write_text(
        f"Utilisateur={DEFAULT_ADMIN_USERNAME}\nPIN={pin}\n",
        encoding="utf-8",
    )
    return pin


def _exec(conn, query: str, params: tuple = ()):
    if hasattr(conn, "execute"):
        try:
            return conn.execute(query, params)
        except Exception:
            if hasattr(conn, "exec_driver_sql"):
                return conn.exec_driver_sql(query, params)
            raise
    if hasattr(conn, "exec_driver_sql"):
        return conn.exec_driver_sql(query, params)
    return conn.cursor().execute(query, params)


def _seed_default_settings(conn) -> None:
    defaults = (
        ("gdrive_backup_dir", ""),
        ("backup_snapshot_time", "02:00"),
        ("backup_local_retention", "30"),
        ("backup_event_retention", "100"),
        ("backup_last_nightly_date", ""),
    )
    for key, value in defaults:
        _exec(
            conn,
            "INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )


def _seed_default_admin(conn) -> None:
    if (
        str(DEFAULT_ADMIN_PASSWORD or "").strip().lower() == "admin"
        and settings.env == "production"
        and not settings.desktop_mode
    ):
        raise RuntimeError(
            "DEFAULT_ADMIN_PASSWORD cannot be 'admin' in production server mode. Set a strong password in your .env file."
        )
    admin = _exec(conn, "SELECT id, password_hash FROM users WHERE username = %s", (DEFAULT_ADMIN_USERNAME,)).fetchone()
    init_pwd = initial_admin_password()
    if not admin:
        res = _exec(
            conn,
            "SELECT data_type FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'must_change_password'",
        ).fetchone()
        is_boolean = res and res[0].upper() == "BOOLEAN"

        val_must_change = False if is_boolean else 0
        val_is_active = True if is_boolean else 1

        _exec(
            conn,
            """
            INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
            VALUES (%s, %s, 'admin', %s, %s, CURRENT_TIMESTAMP)
            """,
            (DEFAULT_ADMIN_USERNAME, generate_password_hash(init_pwd), val_must_change, val_is_active),
        )


def _seed_other_operation(conn) -> None:
    row = _exec(
        conn,
        "SELECT id FROM raw_materials WHERE lower(trim(name)) = lower(trim(%s)) ORDER BY id LIMIT 1",
        (OTHER_OPERATION_NAME,),
    ).fetchone()
    if row:
        raw_id = row["id"] if isinstance(row, dict) else (getattr(row, "id", None) if hasattr(row, "id") else row[0])
        _exec(
            conn,
            "UPDATE raw_materials SET name = %s, unit = %s WHERE id = %s",
            (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT, int(raw_id)),
        )
        return
    _exec(
        conn,
        """
        INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty)
        VALUES (%s, %s, 0, 0, 0, 0, 0)
        """,
        (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT),
    )


def seed_default_data(conn) -> None:
    """Seeds initial administrative user, application settings, and system constants."""
    try:
        _seed_default_admin(conn)
        _seed_default_settings(conn)
        _seed_other_operation(conn)
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception as exc:
        logger.warning("Notice during default data seeding: %s", exc)


def bootstrap_and_migrate() -> None:
    """Single point of entry to initialize schema via Alembic and seed default data."""
    global _BOOTSTRAPPED
    with _BOOTSTRAP_LOCK:
        if _BOOTSTRAPPED:
            return
        ensure_runtime_dirs()
        run_alembic_upgrade()

        engine = get_database_engine(settings.database_url)
        try:
            with engine.connect() as conn:
                seed_default_data(conn)
        except Exception as exc:
            logger.warning("Database seeding post-migration warning: %s", exc)

        _BOOTSTRAPPED = True


def healthcheck() -> bool:
    """Perform a basic connectivity check to the database."""
    try:
        engine = get_database_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database healthcheck failed: %s", e)
        return False


# Compatibility aliases for legacy tests
sys.modules.setdefault("app.core.db_helpers", sys.modules[__name__])
sys.modules.setdefault("app.core.db_helpers.manager", sys.modules[__name__])
sys.modules.setdefault("app.core.db_helpers.execute", sys.modules[__name__])
sys.modules.setdefault("app.core.db_helpers.query", sys.modules[__name__])

