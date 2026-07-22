from __future__ import annotations

import os
import logging
import threading
from time import monotonic
from contextlib import contextmanager
from collections import OrderedDict
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.perf_cache import invalidate_cache_domains
from app.core.request_state import ensure_request_state, get_request_state

logger = logging.getLogger("fabouanes")
_PERF_LOGGER = logging.getLogger("fabouanes.performance")


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

    @property
    def rowcount(self):
        return getattr(self.cursor, "rowcount", -1)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def _clean_params(params):
    if not params:
        return params
    from decimal import Decimal
    if not isinstance(params, (tuple, list)):
        if isinstance(params, dict):
            return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in params.items()}
        if isinstance(params, Decimal):
            return float(params)
        return params
    cleaned = []
    for p in params:
        if isinstance(p, Decimal):
            cleaned.append(float(p))
        elif isinstance(p, list):
            cleaned.append([float(x) if isinstance(x, Decimal) else x for x in p])
        elif isinstance(p, tuple):
            cleaned.append(tuple(float(x) if isinstance(x, Decimal) else x for x in p))
        else:
            cleaned.append(p)
    return tuple(cleaned) if isinstance(params, tuple) else cleaned


def _register_sqlite_custom_functions(dbapi_conn):
    try:
        def _sqlite_regexp_replace(text, pattern, replacement, flags=""):
            if text is None:
                return None
            import re
            flg = re.IGNORECASE if "i" in str(flags) else 0
            return re.sub(pattern, replacement, str(text), flags=flg)

        def _sqlite_date_trunc(field, text):
            if text is None:
                return None
            from datetime import datetime
            try:
                s_text = str(text)
                if s_text.lower() in ("current_date", "now()"):
                    dt = datetime.now()
                else:
                    dt = datetime.fromisoformat(s_text.replace("Z", "+00:00"))
                f = str(field).lower().strip("'\"")
                if f == "month":
                    return dt.strftime("%Y-%m-01 00:00:00")
                if f == "year":
                    return dt.strftime("%Y-01-01 00:00:00")
                if f == "day":
                    return dt.strftime("%Y-%m-%d 00:00:00")
                return s_text
            except Exception:
                return str(text)

        def _sqlite_concat(*args):
            return "".join(str(a) for a in args if a is not None)

        if hasattr(dbapi_conn, "create_function"):
            dbapi_conn.create_function("regexp_replace", 3, _sqlite_regexp_replace)
            dbapi_conn.create_function("regexp_replace", 4, _sqlite_regexp_replace)
            dbapi_conn.create_function("date_trunc", 2, _sqlite_date_trunc)
            dbapi_conn.create_function("concat", -1, _sqlite_concat)
    except Exception:
        pass


def _translate_query_for_sqlite(query: str, has_params: bool = True) -> str:
    """Translate PostgreSQL SQL constructs to SQLite equivalents.

    Applied transparently to every raw SQL string before execution so that
    legacy PG-style queries work without touching each call-site.
    """
    if not isinstance(query, str):
        query = str(query)

    import re

    # 1. PostgreSQL typecasts  (::numeric, ::text, ::jsonb, …)
    query = re.sub(r'::[a-zA-Z0-9_ ]+', '', query)

    # 2. %s → ? placeholder normalisation
    if has_params and "%s" in query:
        query = query.replace("%s", "?")

    # 3. NOW() → CURRENT_TIMESTAMP
    query = re.sub(r'\bNOW\s*\(\s*\)', 'CURRENT_TIMESTAMP', query, flags=re.I)

    # 4. ILIKE → LIKE  (SQLite LIKE is already case-insensitive for ASCII)
    query = re.sub(r'\bILIKE\b', 'LIKE', query, flags=re.I)

    # 5. INTERVAL arithmetic  e.g.  NOW() - INTERVAL '7 days'  /  NOW() - 7 * INTERVAL '1 second'
    #    Convert to SQLite datetime() arithmetic:
    #       CURRENT_TIMESTAMP - INTERVAL 'N unit' → datetime(CURRENT_TIMESTAMP, '-N unit')
    #    Simple scalar form: X - N * INTERVAL '1 second' → datetime(X, '-N seconds')
    def _replace_interval(m):
        value = m.group(1).strip()          # e.g. "7 days" or "1 day" or "24 hours"
        parts = value.split()
        if len(parts) >= 2:
            num, unit = parts[0], parts[1].rstrip("'\"")
            return f"datetime(CURRENT_TIMESTAMP, '-{num} {unit}')"
        return f"datetime(CURRENT_TIMESTAMP, '-{value}')"

    query = re.sub(
        r"CURRENT_TIMESTAMP\s*-\s*INTERVAL\s*'([^']+)'",
        _replace_interval,
        query,
        flags=re.I,
    )
    # N * INTERVAL '1 second' pattern (rate-limiter style)
    query = re.sub(
        r"CURRENT_TIMESTAMP\s*-\s*(\w+)\s*\*\s*INTERVAL\s*'1 second'",
        lambda m: f"datetime(CURRENT_TIMESTAMP, '-' || {m.group(1)} || ' seconds')",
        query,
        flags=re.I,
    )

    # 6. EXTRACT(EPOCH FROM col) → strftime('%s', col)
    query = re.sub(
        r"EXTRACT\s*\(\s*EPOCH\s+FROM\s+([^)]+)\)",
        lambda m: f"strftime('%s', {m.group(1).strip()})",
        query,
        flags=re.I,
    )
    # Other EXTRACT forms: EXTRACT(YEAR/MONTH/DAY FROM col)
    _extract_map = {'year': '%Y', 'month': '%m', 'day': '%d', 'hour': '%H', 'minute': '%M', 'second': '%S'}
    def _replace_extract(m):
        part = m.group(1).lower().strip()
        col  = m.group(2).strip()
        fmt  = _extract_map.get(part)
        if fmt:
            return f"CAST(strftime('{fmt}', {col}) AS INTEGER)"
        return m.group(0)
    query = re.sub(
        r"EXTRACT\s*\(\s*(\w+)\s+FROM\s+([^)]+)\)",
        _replace_extract,
        query,
        flags=re.I,
    )

    # 7. to_char(col, fmt) → strftime(sqlite_fmt, col)
    _pg_to_sqlite_fmt = {
        "YYYY-MM":    "%Y-%m",
        "YYYY":       "%Y",
        "MM":         "%m",
        "DD":         "%d",
        "YYYY-MM-DD": "%Y-%m-%d",
    }
    def _replace_to_char(m):
        col = m.group(1).strip()
        fmt = m.group(2).strip().strip("'\"")
        sqlite_fmt = _pg_to_sqlite_fmt.get(fmt, "%Y-%m")
        return f"strftime('{sqlite_fmt}', {col})"
    query = re.sub(
        r"to_char\s*\(\s*([^,]+),\s*'([^']+)'\s*\)",
        _replace_to_char,
        query,
        flags=re.I,
    )

    # 8. RETURNING id → stripped (SQLite 3.35+ supports it, but older builds don't;
    #    lastrowid is used instead — strip to keep compatibility)
    query = re.sub(r'\s+RETURNING\s+\w+\s*$', '', query, flags=re.I)

    # 9. TRUE/FALSE literals → 1/0  (SQLite has no boolean keywords pre-3.23)
    query = re.sub(r'\bTRUE\b', '1', query, flags=re.I)
    query = re.sub(r'\bFALSE\b', '0', query, flags=re.I)

    return query


class CompatConnection:
    def __init__(
        self,
        conn,
        dialect: str = "sqlite",
        on_close: Callable[[Any], None] | None = None,
        reconnect: Callable[[], Any] | None = None,
    ):
        self.conn = conn
        self.dialect = dialect or "sqlite"
        self._on_close = on_close
        self._reconnect = reconnect
        self._closed = False
        _register_sqlite_custom_functions(self.conn)

    def execute(self, query: str, params: tuple = ()):
        if not isinstance(query, str):
            query = str(query)
        retried = False
        cleaned_params = _clean_params(params)
        
        is_sqlite = (
            self.dialect == "sqlite"
            or "sqlite" in type(self.conn).__module__.lower()
            or "sqlite" in type(getattr(self.conn, "dbapi_connection", self.conn)).__module__.lower()
        )
        if is_sqlite:
            query = _translate_query_for_sqlite(query, bool(cleaned_params))

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
                is_lock = "database is locked" in exc_msg or "locked" in exc_msg or "busy" in exc_msg or "25p02" in exc_msg or "transaction is aborted" in exc_msg
                if is_lock and not retried:
                    retried = True
                    import time
                    time.sleep(0.1)
                    continue

                if not retried and self._reconnect is not None:
                    from sqlalchemy.exc import DBAPIError, OperationalError
                    if isinstance(exc, (OperationalError, DBAPIError)) or "connection" in exc_msg:
                        self._reset_db_connection()
                        retried = True
                        continue
                raise

    def _reset_db_connection(self) -> None:
        if self._reconnect is None:
            raise RuntimeError("Connexion base de données perdue et reconnexion indisponible.")
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = self._reconnect()

    def executescript(self, script: str):
        from app.core.db_helpers.query import split_sql_script
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
        self._perf_shutdown = False

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
        if url.startswith("sqlite+aiosqlite://"):
            return "sqlite://" + url[len("sqlite+aiosqlite://") :]
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            from app.core.config import settings
            data_dir = settings.app_data_dir
            db_path = (data_dir / "fabouanes.db").resolve().as_posix()
            return f"sqlite:///{db_path}"
        return url if url else f"sqlite:///{(settings.app_data_dir / 'fabouanes.db').resolve().as_posix()}"

    def create_database_engine(self, database_url: str) -> Engine:
        engine_url = self.sqlalchemy_database_url(database_url)
        if "sqlite" in engine_url:
            engine = create_engine(
                engine_url,
                future=True,
                connect_args={"check_same_thread": False, "timeout": 30.0},
            )
        else:
            engine = create_engine(
                engine_url,
                future=True,
                pool_pre_ping=True,
                pool_size=self._env_int("FAB_PG_POOL_SIZE", 10, 1, 200),
                max_overflow=self._env_int("FAB_PG_POOL_MAX_OVERFLOW", 10, 0, 500),
                pool_timeout=self._env_int("FAB_PG_POOL_TIMEOUT", 30, 1, 300),
                pool_recycle=self._env_int("FAB_PG_POOL_RECYCLE_SECONDS", 1800, 60, 86400),
            )

        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("PRAGMA busy_timeout = 30000;")
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA synchronous = NORMAL;")
                cursor.execute("PRAGMA cache_size = -64000;")
                cursor.execute("PRAGMA temp_store = MEMORY;")
                cursor.execute("PRAGMA mmap_size = 268435456;")
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
        try:
            engine = self.get_database_engine(raw_url)
            conn = engine.raw_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("PRAGMA busy_timeout = 30000;")
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA synchronous = NORMAL;")
                cursor.execute("PRAGMA cache_size = -64000;")
                cursor.execute("PRAGMA temp_store = MEMORY;")
                cursor.execute("PRAGMA mmap_size = 268435456;")
            except Exception as e:
                logging.getLogger("fabouanes").debug("Failed to set SQLite pragmas: %s", e)
            finally:
                cursor.close()
        except Exception as e:
            raise RuntimeError(f"Impossible de se connecter a la base de donnees SQLite: {e}") from e

        def _reconnect():
            return engine.raw_connection()

        return CompatConnection(
            conn,
            dialect="sqlite",
            on_close=lambda c: c.close(),
            reconnect=_reconnect,
        )

    def postgres_pool_status(self, database_url: str) -> dict[str, int | str]:
        pool = self.get_database_engine(database_url).pool
        status: dict[str, int | str] = {"engine": "sqlite"}
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
        if any(table in q for table in (" users", " backup_jobs", " audit_logs", " activity_logs", " system_logs", " error_logs")):
            domains.add("admin")
        if domains:
            invalidate_cache_domains(*domains)

    MAX_UNPAGINATED_ROWS = 10_000

    def _guard_pagination(self, query: str) -> str:
        q = query.strip().lower()
        if not q.startswith("select") and not q.startswith("("):
            return query
        if "count(*)" in q or "count(1)" in q:
            return query
        try:
            import sqlglot
            from sqlglot import exp
            parsed = sqlglot.parse_one(query, read="sqlite")
            if isinstance(parsed, (exp.Select, exp.Union)):
                if not parsed.args.get("limit"):
                    logger.debug("[PAGINATION GUARD] Auto-LIMIT %d via sqlglot appliqué.", self.MAX_UNPAGINATED_ROWS)
                    return parsed.limit(self.MAX_UNPAGINATED_ROWS).sql(dialect="sqlite")
        except Exception as exc:
            logger.warning("[PAGINATION GUARD] Fallback sur erreur de parsing sqlglot: %s", exc)

        if any(kw in q for kw in ("limit ", "limit\n", "for update", "for share")):
            return query
        logger.debug("[PAGINATION GUARD] Auto-LIMIT %d appliqué à: %s", self.MAX_UNPAGINATED_ROWS, query[:120])
        return f"{query.rstrip().rstrip(';')} LIMIT {self.MAX_UNPAGINATED_ROWS}"

    def query_db(self, query: str, params: tuple = (), one: bool = False):
        # Translate any PostgreSQL-specific SQL to SQLite before execution
        query = _translate_query_for_sqlite(query, bool(params))
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
                is_transient = (
                    "connection" in exc_msg
                    or "database is locked" in exc_msg
                    or "disk i/o error" in exc_msg
                    or "locked" in exc_msg
                    or "busy" in exc_msg
                    or "57p01" in exc_msg
                    or "08006" in exc_msg
                    or "08001" in exc_msg
                )
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
        import asyncio
        return await asyncio.to_thread(self.query_db, query, params, one)

    def execute_db(self, query: str, params: tuple = ()) -> int:
        import re
        # Translate any PostgreSQL-specific SQL to SQLite before execution
        query = _translate_query_for_sqlite(query, bool(params))
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
                    if query.strip().upper().startswith(("DELETE", "UPDATE")):
                        last_id = cur.rowcount
                    else:
                        last_id = cur.lastrowid
                if self._tx_depth() == 0:
                    db.commit()
                cur.close()
            except Exception as exc:
                exc_msg = str(exc).lower()
                is_transient = (
                    "connection" in exc_msg
                    or "database is locked" in exc_msg
                    or "disk i/o error" in exc_msg
                    or "locked" in exc_msg
                    or "busy" in exc_msg
                    or "57p01" in exc_msg
                    or "08006" in exc_msg
                    or "08001" in exc_msg
                )
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
                    last_id = self._fallback_last_insert_id(db, query)
                self._record_sql_timing(query, params, (monotonic() - started) * 1000.0)
                self._invalidate_after_write(query)
                return int(last_id or 0)
        return 0

    async def execute_db_async(self, query: str, params: tuple = ()) -> int:
        import asyncio
        return await asyncio.to_thread(self.execute_db, query, params)

    def _fallback_last_insert_id(self, db, query: str) -> int:
        try:
            cur = db.execute("SELECT last_insert_rowid()")
            row = cur.fetchone()
            cur.close()
            return int(row[0] if row and row[0] is not None else 0)
        except Exception:
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
        try:
            cur = conn.execute(f"PRAGMA table_info({table})")
            rows = cur.fetchall()
            cur.close()
            cols = set()
            for r in rows:
                if isinstance(r, dict):
                    name = r.get("name") or r.get("column_name")
                elif hasattr(r, "keys"):
                    keys = list(r.keys())
                    name = r["name"] if "name" in keys else (r["column_name"] if "column_name" in keys else r[0])
                else:
                    name = r[1] if len(r) > 1 else r[0]
                if name:
                    cols.add(name)
            return cols
        except Exception:
            return set()

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
                        (kind, name, float(elapsed_ms), route, details),
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


db_manager = DatabaseManager()


class ConnectionPoolManager(DatabaseManager):
    pass


pool_manager = db_manager


def get_db() -> CompatConnection:
    return db_manager.get_db()


def connect_database(database_url: str) -> CompatConnection:
    return db_manager.connect_database(database_url)


def postgres_pool_status(database_url: str) -> dict[str, int | str]:
    return db_manager.postgres_pool_status(database_url)


def list_columns(conn: CompatConnection, table: str) -> set[str]:
    return db_manager.list_columns(conn, table)


def pending_performance_event_count() -> int:
    return db_manager.pending_performance_event_count()


def drain_performance_events_once() -> int:
    return db_manager.drain_performance_events_once()


def db_task(func):
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


@contextmanager
def db_transaction():
    with db_manager.db_transaction() as tx:
        yield tx


def get_setting(key: str, default: str = '') -> str:
    return db_manager.get_setting(key, default)


def set_setting(key: str, value: str) -> None:
    db_manager.set_setting(key, value)
