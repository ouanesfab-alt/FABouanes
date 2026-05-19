from __future__ import annotations

import os
import re
import logging
import threading
import asyncio
from time import monotonic
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.perf_cache import invalidate_cache_domains
from app.core.request_state import ensure_request_state, get_request_state
from app.core.db_pool import pool_manager, CompatConnection

logger = logging.getLogger("fabouanes")
_PERF_LOGGER = logging.getLogger("fabouanes.performance")

class DatabaseManager:
    def __init__(self):
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

    def get_database_engine(self, database_url: str) -> Engine:
        return pool_manager.get_database_engine(database_url)

    def connect_database(self, database_url: str) -> CompatConnection:
        return pool_manager.connect_database(database_url)

    def get_db(self) -> CompatConnection:
        state = get_request_state()
        if state is not None and getattr(state, "db", None) is not None:
            return state.db
        state = ensure_request_state()
        if getattr(state, "db", None) is None:
            state.db = self.connect_database(settings.database_url)
        return state.db

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
        db = self.get_db()
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
        db = self.get_db()
        started = monotonic()
        
        is_insert = bool(re.match(r"\s*INSERT\s+INTO\s+", str(query or ""), flags=re.I))
        
        adapted_query = query
        has_returning = False
        if is_insert:
            if " returning " not in query.lower():
                match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", str(query or ""), flags=re.I)
                if match:
                    table = match.group(1).lower()
                    if table not in {"app_settings", "schema_migrations"}:
                        adapted_query = query.rstrip().rstrip(";") + " RETURNING id"
                        has_returning = True

        try:
            cur = db.execute(adapted_query, params)
            if has_returning:
                row = cur.fetchone()
                last_id = row[0] if row else None
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
        db = self.get_db()
        previous_depth = self._tx_depth()
        self._set_tx_depth(previous_depth + 1)
        try:
            yield db
        except Exception:
            if previous_depth == 0:
                try:
                    db.rollback()
                except Exception as e2:
                    logger.debug("Ignored error: %s", e2, exc_info=False)
            raise
        else:
            if previous_depth == 0:
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

    def postgres_pool_status(self, database_url: str) -> dict[str, int | str]:
        return pool_manager.postgres_pool_status(database_url)

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
            except Exception:
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

