from __future__ import annotations

import os
import re
import logging
import threading
import asyncio
from time import monotonic
from contextlib import contextmanager
from collections import OrderedDict
from typing import Any, Callable
from urllib.parse import urlparse

from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.perf_cache import invalidate_cache_domains
from app.core.request_state import ensure_request_state, get_request_state

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
        
        # Parse comments ONLY when we are not inside a string or dollar block
        if not in_dollar and not in_single_quote and not in_double_quote:
            # Single-line comment --
            if char == '-' and i + 1 < n and script[i+1] == '-':
                # Skip until end of line
                i += 2
                while i < n and script[i] != '\n':
                    i += 1
                continue
            # Multi-line comment /* ... */
            if char == '/' and i + 1 < n and script[i+1] == '*':
                i += 2
                while i < n and not (script[i] == '*' and i + 1 < n and script[i+1] == '/'):
                    i += 1
                i += 2  # skip closing */
                continue
        
        if char == '$' and i + 1 < n and script[i+1] == '$':
            in_dollar = not in_dollar
            current.append('$$')
            i += 2
            continue
            
        if not in_dollar:
            if char == "'" and (i == 0 or script[i-1] != '\\'):
                in_single_quote = not in_single_quote
            elif char == '"' and (i == 0 or script[i-1] != '\\'):
                in_double_quote = not in_double_quote
                
        if char == ';' and not in_dollar and not in_single_quote and not in_double_quote:
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

class DatabaseManager:
    def __init__(self):
        # Performance monitoring & slow SQL configuration
        self._slow_sql_threshold_ms = float(os.environ.get("FAB_SLOW_SQL_MS", "100") or "100")
        self._perf_queue_maxlen = int(os.environ.get("FAB_PERF_QUEUE_MAXLEN", "1000") or "1000")
        from collections import deque
        self._perf_queue = deque(maxlen=max(100, self._perf_queue_maxlen))
        self._perf_lock = threading.Lock()
        self._perf_event = threading.Event()
        self._perf_worker_started = False
        self._perf_worker_lock = threading.Lock()
        self._perf_conn = None
        self._perf_conn_lock = threading.Lock()

        # Engine pool management
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
        engine = create_engine(
            engine_url,
            future=True,
            pool_pre_ping=True,
            pool_size=self._env_int("FAB_PG_POOL_SIZE", 10, 1, 200),
            max_overflow=self._env_int("FAB_PG_POOL_MAX_OVERFLOW", 10, 0, 500),
            pool_timeout=self._env_int("FAB_PG_POOL_TIMEOUT", 30, 1, 300),
            pool_recycle=self._env_int("FAB_PG_POOL_RECYCLE_SECONDS", 1800, 60, 86400),
        )
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
        try:
            engine = self.get_database_engine(raw_url)
            conn = engine.raw_connection()
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
                    isolation_level="AUTOCOMMIT",
                    future=True,
                )
                with pg_engine.connect() as pg_conn:
                    pg_conn.execute(text(f'CREATE DATABASE "{database}"'))
                pg_engine.dispose()
                
                engine = self.get_database_engine(raw_url)
                conn = engine.raw_connection()
            elif "authentification" in err_msg or "password authentication failed" in err_msg or "28p01" in err_msg:
                raise RuntimeError("Erreur critique d'authentification PostgreSQL. Verifie le mot de passe dans .env") from e
            else:
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
            return state.db
        state = ensure_request_state()
        if getattr(state, "db", None) is None:
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
            return state.read_db
        state = ensure_request_state()
        if getattr(state, "read_db", None) is None:
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
        if any(table in q for table in (" users", " backup_jobs", " audit_logs", " activity_logs", " system_logs", " error_logs")):
            domains.add("admin")
        if domains:
            invalidate_cache_domains(*domains)

    def query_db(self, query: str, params: tuple = (), one: bool = False):
        started = monotonic()
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
        except Exception:
            if self._tx_depth() == 0:
                try:
                    db.rollback()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
            raise

    async def query_db_async(self, query: str, params: tuple = (), one: bool = False):
        return await asyncio.to_thread(self.query_db, query, params, one)

    def execute_db(self, query: str, params: tuple = ()) -> int:
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
        except Exception:
            if self._tx_depth() == 0:
                try:
                    db.rollback()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
            raise

        if not last_id:
            last_id = self._postgres_last_insert_id(db, query)
        self._record_sql_timing(query, params, (monotonic() - started) * 1000.0)
        self._invalidate_after_write(query)
        return int(last_id or 0)


    async def execute_db_async(self, query: str, params: tuple = ()) -> int:
        return await asyncio.to_thread(self.execute_db, query, params)

    def _postgres_last_insert_id(self, db, query: str) -> int:
        match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", str(query or ""), flags=re.I)
        if not match:
            return 0
        table = match.group(1)
        if table in {"app_settings", "schema_migrations"}:
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

    def get_setting(self, key: str, default: str = '') -> str:
        try:
            row = self.query_db('SELECT value FROM app_settings WHERE key = %s', (key,), one=True)
            return row['value'] if row and row['value'] is not None else default
        except Exception as e:
            logger.debug("Ignored error: %s", e, exc_info=False)
            return default

    def set_setting(self, key: str, value: str) -> None:
        self.execute_db(
            'INSERT INTO app_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP',
            (key, value)
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
            if self._perf_conn is None:
                self._perf_conn = self.connect_database(settings.database_url)
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
                logger.warning("Échec de l'écriture du lot de logs de performance: %s", e)
                try:
                    self._perf_conn.close()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
                self._perf_conn = None
                raise

    def _performance_worker(self) -> None:
        while True:
            self._perf_event.wait(timeout=2.0)
            self._perf_event.clear()
            while True:
                batch = self._pop_performance_batch()
                if not batch:
                    break
                try:
                    self._write_performance_batch(batch)
                except Exception:
                    _PERF_LOGGER.exception("Unable to persist performance log batch")

    def pending_performance_event_count(self) -> int:
        with self._perf_lock:
            return len(self._perf_queue)

    def drain_performance_events_once(self) -> int:
        batch = self._pop_performance_batch(500)
        self._write_performance_batch(batch)
        return len(batch)

db_manager = DatabaseManager()

# Backwards compatibility facades
class ConnectionPoolManager(DatabaseManager):
    pass

pool_manager = db_manager

logger = logging.getLogger("fabouanes")
_PERF_LOGGER = logging.getLogger("fabouanes.performance")



def get_db() -> CompatConnection:
    return db_manager.get_db()

def connect_database(database_url: str) -> CompatConnection:
    return db_manager.connect_database(database_url)

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

@contextmanager
def db_transaction():
    with db_manager.db_transaction() as tx:
        yield tx

def get_setting(key: str, default: str = '') -> str:
    return db_manager.get_setting(key, default)

def set_setting(key: str, value: str) -> None:
    db_manager.set_setting(key, value)

def postgres_pool_status(database_url: str) -> dict[str, int | str]:
    return db_manager.postgres_pool_status(database_url)

def list_columns(conn: CompatConnection, table: str) -> set[str]:
    return db_manager.list_columns(conn, table)

def pending_performance_event_count() -> int:
    return db_manager.pending_performance_event_count()

def drain_performance_events_once() -> int:
    return db_manager.drain_performance_events_once()

def db_task(func):
    """
    Decorator to wrap synchronous repository or database operations.
    Runs synchronously by default when called normally:
        result = get_client(123)
        
    Runs in a background thread when called via the .async_ attribute:
        result = await get_client.async_(123)
    """
    import functools
    import asyncio
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
        
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
        
    wrapper.async_ = async_wrapper
    wrapper.sync = func
    return wrapper


def execute_sa(query) -> int:
    from sqlalchemy.dialects import postgresql
    compiled = query.compile(dialect=postgresql.dialect(paramstyle="format"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in compiled.positiontup)
    return execute_db(sql, params)


def query_sa(query, one: bool = False):
    from sqlalchemy.dialects import postgresql
    compiled = query.compile(dialect=postgresql.dialect(paramstyle="format"), compile_kwargs={"literal_binds": False})
    sql = str(compiled)
    params = tuple(compiled.params[name] for name in compiled.positiontup)
    return query_db(sql, params, one=one)

