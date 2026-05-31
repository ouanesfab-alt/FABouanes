from __future__ import annotations

import csv
import io
import json
import threading
from collections import deque
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.core.request_state import get_state_value

import time
from app.core.db_access import execute_db, query_db

import asyncio
from app.core.db_access import query_db, execute_db_async

_AUDIT_QUEUE: asyncio.Queue | None = None
_AUDIT_TASK: asyncio.Task | None = None
_AUDIT_DROPPED = 0
_last_warned_ts = 0.0

def _get_audit_queue() -> asyncio.Queue:
    global _AUDIT_QUEUE
    if _AUDIT_QUEUE is None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        _AUDIT_QUEUE = asyncio.Queue(maxsize=50000)
    return _AUDIT_QUEUE

def start_audit_worker() -> None:
    global _AUDIT_TASK
    if _AUDIT_TASK is not None:
        return
    try:
        loop = asyncio.get_running_loop()
        _AUDIT_TASK = loop.create_task(_audit_flusher_task())
    except RuntimeError:
        pass

async def stop_audit_worker() -> None:
    global _AUDIT_TASK
    if _AUDIT_TASK is None:
        return
    _AUDIT_TASK.cancel()
    try:
        await _AUDIT_TASK
    except asyncio.CancelledError:
        pass
    _AUDIT_TASK = None

async def _audit_flusher_task() -> None:
    import logging
    logger = logging.getLogger("fabouanes.audit")
    queue = _get_audit_queue()
    while True:
        try:
            item = await queue.get()
            batch = [item]
            while not queue.empty() and len(batch) < 50:
                try:
                    batch.append(queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            
            for row in batch:
                try:
                    await execute_db_async(
                        """
                        INSERT INTO audit_logs (
                            actor_user_id, actor_username, actor_role, source,
                            action, entity_type, entity_id, status,
                            ip_address, user_agent, request_id,
                            before_json, after_json, meta_json, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        """,
                        row
                    )
                except Exception:
                    logger.exception("Unable to persist audit log row")
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in audit flusher task")
            await asyncio.sleep(2.0)



SENSITIVE_TOKENS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "refresh_token",
    "access_token",
    "client_secret",
    "api_key",
    "authorization",
}


import decimal

def row_to_dict(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return {key: row_to_dict(value) for key, value in row.items()}
    if hasattr(row, "keys"):
        return {key: row_to_dict(row[key]) for key in row.keys()}
    if isinstance(row, (list, tuple)):
        return [row_to_dict(item) for item in row]
    if isinstance(row, datetime):
        return row.isoformat()
    if isinstance(row, decimal.Decimal):
        return float(row)
    return row


def _sanitize_key(key: str, value: Any) -> Any:
    normalized = key.lower()
    if any(token in normalized for token in SENSITIVE_TOKENS):
        return "[redacted]"
    return sanitize_payload(value)


def sanitize_payload(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {str(key): _sanitize_key(str(key), item) for key, item in value.items()}
    if hasattr(value, "keys"):
        return {str(key): _sanitize_key(str(key), value[key]) for key in value.keys()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(sanitize_payload(row_to_dict(value)), ensure_ascii=False, sort_keys=True, default=str)


def _resolve_actor(user_id: int | None = None, actor: Any = None) -> tuple[int | None, str, str]:
    resolved_id = user_id
    resolved_username = None
    resolved_role = None

    if actor:
        if isinstance(actor, Mapping):
            resolved_id = actor.get("id") or resolved_id
            resolved_username = actor.get("username")
            resolved_role = actor.get("role")
        else:
            resolved_id = getattr(actor, "id", None) or resolved_id
            resolved_username = getattr(actor, "username", None)
            resolved_role = getattr(actor, "role", None)

    if resolved_id is None and not resolved_username:
        state_user = get_state_value("user")
        if state_user:
            if isinstance(state_user, Mapping):
                resolved_id = state_user.get("id")
                resolved_username = state_user.get("username")
                resolved_role = state_user.get("role")
            else:
                resolved_id = getattr(state_user, "id", None)
                resolved_username = getattr(state_user, "username", None)
                resolved_role = getattr(state_user, "role", None)

    if resolved_id and (not resolved_username or not resolved_role):
        try:
            from app.repositories.user_repository import get_user_by_id
            user = get_user_by_id(resolved_id)
            if user:
                resolved_username = resolved_username or user.get("username")
                resolved_role = resolved_role or user.get("role")
        except Exception as e:
            import logging
            logging.getLogger("fabouanes.audit").warning("Impossible de charger l'utilisateur pour l'audit: %s", e)

    return resolved_id, resolved_username or "anonymous", resolved_role or "anonymous"


def audit_event(
    action: str,
    entity_type: str = "",
    entity_id: Any = None,
    *,
    status: str = "success",
    before: Any = None,
    after: Any = None,
    meta: Any = None,
    source: str | None = None,
    actor: Mapping[str, Any] | None = None,
) -> None:
    actor_user_id, actor_username, actor_role = _resolve_actor(actor=actor)
    request_id = get_state_value("request_id")
    request_source = source or get_state_value("audit_source")
    remote_addr = ""
    user_agent = ""
    state_request = get_state_value("request")
    if state_request is not None:
        request_source = request_source or ("api" if state_request.url.path.startswith("/api/") else "web")
        forwarded = state_request.headers.get("X-Forwarded-For", "")
        remote_addr = (forwarded.split(",", 1)[0].strip() if forwarded else "") or (getattr(getattr(state_request, "client", None), "host", "") or "")
        user_agent = state_request.headers.get("User-Agent", "")[:500]
    else:
        request_source = request_source or "system"
    params = (
        actor_user_id,
        actor_username or "anonymous",
        actor_role or "anonymous",
        request_source,
        action,
        entity_type,
        "" if entity_id is None else str(entity_id),
        status,
        remote_addr,
        user_agent,
        request_id,
        _json_dump(before),
        _json_dump(after),
        _json_dump(meta),
    )
    global _last_warned_ts, _AUDIT_DROPPED
    global _last_warned_ts, _AUDIT_DROPPED
    queue = _get_audit_queue()
    if queue.full():
        _AUDIT_DROPPED += 1
        import logging
        logging.getLogger("fabouanes.audit").error(
            "Audit log queue is full! Dropped event. Total dropped = %d", _AUDIT_DROPPED
        )
    else:
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(queue.put_nowait, params)
        except RuntimeError:
            queue.put_nowait(params)

        q_len = queue.qsize()
        if q_len > 5000:
            now = time.time()
            if now - _last_warned_ts > 60.0:
                _last_warned_ts = now
                import logging
                logging.getLogger("fabouanes.audit").warning(
                    "Audit queue high-watermark exceeded: current size is %d. The database writer is falling behind.",
                    q_len
                )


def list_audit_logs(filters: Mapping[str, Any] | None = None, *, limit: int = 200):
    filters = filters or {}
    where: list[str] = []
    params: list[Any] = []
    if filters.get("date_from"):
        where.append("CAST(created_at AS DATE) >= CAST(%s AS DATE)")
        params.append(str(filters["date_from"]))
    if filters.get("date_to"):
        where.append("CAST(created_at AS DATE) <= CAST(%s AS DATE)")
        params.append(str(filters["date_to"]))
    if filters.get("actor"):
        where.append("lower(actor_username) LIKE lower(%s)")
        params.append(f"%{filters['actor']}%")
    if filters.get("action"):
        where.append("lower(action) LIKE lower(%s)")
        params.append(f"%{filters['action']}%")
    if filters.get("entity_type"):
        where.append("lower(entity_type) LIKE lower(%s)")
        params.append(f"%{filters['entity_type']}%")
    if filters.get("status"):
        where.append("status = %s")
        params.append(str(filters["status"]))
    query = """
        SELECT *
        FROM audit_logs
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT %s"
    params.append(int(limit))
    return [dict(row) for row in query_db(query, tuple(params))]


def export_audit_logs_csv(filters: Mapping[str, Any] | None = None, *, limit: int = 1000) -> bytes:
    rows = list_audit_logs(filters, limit=limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "created_at",
            "actor_username",
            "actor_role",
            "source",
            "action",
            "entity_type",
            "entity_id",
            "status",
            "ip_address",
            "request_id",
            "before_json",
            "after_json",
            "meta_json",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("created_at"),
                row.get("actor_username"),
                row.get("actor_role"),
                row.get("source"),
                row.get("action"),
                row.get("entity_type"),
                row.get("entity_id"),
                row.get("status"),
                row.get("ip_address"),
                row.get("request_id"),
                row.get("before_json"),
                row.get("after_json"),
                row.get("meta_json"),
            ]
        )
    return output.getvalue().encode("utf-8")


def audit_delete_event(
    entity_type: str,
    entity_id: int,
    snapshot: dict,
    user_id: int | None = None,
) -> None:
    """
    Trace une suppression dans audit_logs.
    snapshot = état de l'entité AVANT suppression.
    """
    resolved_user_id, actor_username, actor_role = _resolve_actor(user_id=user_id)
    audit_event(
        action="delete",
        entity_type=entity_type,
        entity_id=entity_id,
        before=snapshot,
        actor={"id": resolved_user_id, "username": actor_username, "role": actor_role} if resolved_user_id else None,
    )
