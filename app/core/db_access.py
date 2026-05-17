from __future__ import annotations

import os
import re
import logging
import threading
import asyncio
from functools import partial
from collections import deque
from time import monotonic
from contextlib import contextmanager

from app.core.config import settings
from app.core.db import connect_database
from app.core.perf_cache import invalidate_cache_domains
from app.core.request_state import ensure_request_state, get_request_state

logger = logging.getLogger("fabouanes")

async def query_db_async(query: str, params: tuple = (), one: bool = False):
    return await asyncio.to_thread(query_db, query, params, one)

async def execute_db_async(query: str, params: tuple = ()) -> int:
    return await asyncio.to_thread(execute_db, query, params)

_SLOW_SQL_THRESHOLD_MS = float(os.environ.get("FAB_SLOW_SQL_MS", "100") or "100")
_PERF_LOGGER = logging.getLogger("fabouanes.performance")
_PERF_QUEUE_MAXLEN = int(os.environ.get("FAB_PERF_QUEUE_MAXLEN", "1000") or "1000")
_PERF_QUEUE: deque[tuple[str, str, float, str, str]] = deque(maxlen=max(100, _PERF_QUEUE_MAXLEN))
_PERF_LOCK = threading.Lock()
_PERF_EVENT = threading.Event()
_PERF_WORKER_STARTED = False
_PERF_WORKER_LOCK = threading.Lock()

def get_db():
    state = get_request_state()
    if state is not None and getattr(state, "db", None) is not None:
        return state.db
    state = ensure_request_state()
    if getattr(state, "db", None) is None:
        state.db = connect_database(_database_url())
    return state.db


def _database_url() -> str:
    return settings.database_url


def _tx_depth() -> int:
    state = get_request_state()
    if state is not None:
        return int(getattr(state, "db_tx_depth", 0) or 0)
    return 0


def _set_tx_depth(value: int) -> None:
    state = ensure_request_state()
    state.db_tx_depth = value

def _route_label() -> str:
    state = get_request_state()
    state_request = getattr(state, "request", None) if state is not None else None
    if state_request is None:
        return ""
    route = state_request.scope.get("route")
    endpoint = getattr(route, "name", "") or state_request.scope.get("endpoint_name", "")
    path = state_request.url.path
    return f"{state_request.method} {path}" if not endpoint else f"{state_request.method} {path} ({endpoint})"


def _record_performance_event(kind: str, name: str, elapsed_ms: float, details: str = "") -> None:
    if "performance_logs" in name.lower() or elapsed_ms <= 0:
        return
    event = (kind[:40], name[:240], float(elapsed_ms), _route_label()[:300], details[:1000])
    with _PERF_LOCK:
        _PERF_QUEUE.append(event)
    _PERF_LOGGER.warning("%s %.2fms %s %s", kind, elapsed_ms, name[:240], details[:200])
    _ensure_performance_worker()
    _PERF_EVENT.set()


def _record_sql_timing(query: str, params: tuple, elapsed_ms: float) -> None:
    if elapsed_ms < _SLOW_SQL_THRESHOLD_MS:
        return
    normalized = " ".join(str(query or "").split())
    _record_performance_event("sql", normalized, elapsed_ms, f"params={len(params or ())}")


def _invalidate_after_write(query: str) -> None:
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
    if any(table in q for table in (" users", " backup_jobs", " audit_logs", " activity_logs", " system_logs", " error_logs")):
        domains.add("admin")
    if domains:
        invalidate_cache_domains(*domains)


def query_db(query: str, params: tuple = (), one: bool = False):
    started = monotonic()
    db = get_db()
    try:
        cur = db.execute(query, params)
        if one:
            result = cur.fetchone()
        else:
            result = cur.fetchall()
        cur.close()
        _record_sql_timing(query, params, (monotonic() - started) * 1000.0)
        return result
    except Exception:
        if _tx_depth() == 0:
            try:
                db.rollback()
            except Exception as e2:
                logger.debug("Ignored error: %s", e2, exc_info=False)
        raise


def execute_db(query: str, params: tuple = ()) -> int:
    db = get_db()
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
            
        if _tx_depth() == 0:
            db.commit()
        cur.close()
    except Exception:
        if _tx_depth() == 0:
            try:
                db.rollback()
            except Exception as e2:
                logger.debug("Ignored error: %s", e2, exc_info=False)
        raise

    if not last_id:
        last_id = _postgres_last_insert_id(db, query)
    _record_sql_timing(query, params, (monotonic() - started) * 1000.0)
    _invalidate_after_write(query)
    return int(last_id or 0)


def _postgres_last_insert_id(db, query: str) -> int:
    match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", str(query or ""), flags=re.I)
    if not match:
        return 0
    table = match.group(1)
    if table in {"app_settings", "schema_migrations"}:
        return 0
    try:
        cur = db.execute("SELECT currval(pg_get_serial_sequence(?, 'id')) AS id", (table,))
        row = cur.fetchone()
        cur.close()
        return int(row["id"] if row else 0)
    except Exception as e:
        logger.debug("Ignored error: %s", e, exc_info=False)
        return 0


def explain_query_plan(query: str, params: tuple = ()) -> list[dict]:
    db = get_db()
    prefix = "EXPLAIN "
    cur = db.execute(prefix + query, params)
    try:
        rows = cur.fetchall()
        return [dict(row) if hasattr(row, "keys") else {"plan": str(row)} for row in rows]
    finally:
        cur.close()

@contextmanager
def db_transaction():
    db = get_db()
    previous_depth = _tx_depth()
    _set_tx_depth(previous_depth + 1)
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
        _set_tx_depth(previous_depth)

def get_setting(key: str, default: str = '') -> str:
    try:
        row = query_db('SELECT value FROM app_settings WHERE key = ?', (key,), one=True)
        return row['value'] if row and row['value'] is not None else default
    except Exception as e:
        logger.debug("Ignored error: %s", e, exc_info=False)
        return default

def set_setting(key: str, value: str) -> None:
    execute_db('INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP', (key, value))


def _ensure_performance_worker() -> None:
    global _PERF_WORKER_STARTED
    if os.environ.get("FAB_DISABLE_PERFORMANCE_DB_LOGS", "0").strip() == "1":
        return
    if _PERF_WORKER_STARTED:
        return
    with _PERF_WORKER_LOCK:
        if _PERF_WORKER_STARTED:
            return
        thread = threading.Thread(target=_performance_worker, name="fab-performance-log-writer", daemon=True)
        thread.start()
        _PERF_WORKER_STARTED = True


def _pop_performance_batch(limit: int = 50) -> list[tuple[str, str, float, str, str]]:
    batch: list[tuple[str, str, float, str, str]] = []
    with _PERF_LOCK:
        while _PERF_QUEUE and len(batch) < limit:
            batch.append(_PERF_QUEUE.popleft())
    return batch


_PERF_CONN = None
_PERF_CONN_LOCK = threading.Lock()


def _write_performance_batch(batch: list[tuple[str, str, float, str, str]]) -> None:
    global _PERF_CONN
    if not batch:
        return
    with _PERF_CONN_LOCK:
        if _PERF_CONN is None:
            _PERF_CONN = connect_database(_database_url())
        try:
            for kind, name, elapsed_ms, route, details in batch:
                cur = _PERF_CONN.execute(
                    """
                    INSERT INTO performance_logs (kind, name, elapsed_ms, route, details, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (kind, name, elapsed_ms, route, details),
                )
                cur.close()
            _PERF_CONN.commit()
        except Exception:
            try:
                _PERF_CONN.close()
            except Exception as e2:
                logger.debug("Ignored error: %s", e2, exc_info=False)
            _PERF_CONN = None
            raise


def _performance_worker() -> None:
    while True:
        _PERF_EVENT.wait(timeout=2.0)
        _PERF_EVENT.clear()
        while True:
            batch = _pop_performance_batch()
            if not batch:
                break
            try:
                _write_performance_batch(batch)
            except Exception:
                _PERF_LOGGER.exception("Unable to persist performance log batch")


def pending_performance_event_count() -> int:
    with _PERF_LOCK:
        return len(_PERF_QUEUE)


def drain_performance_events_once() -> int:
    batch = _pop_performance_batch(500)
    _write_performance_batch(batch)
    return len(batch)
