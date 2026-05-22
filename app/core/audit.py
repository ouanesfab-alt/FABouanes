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

from app.core.db_access import execute_db, query_db

_AUDIT_QUEUE: deque[tuple] = deque(maxlen=2000)
_AUDIT_LOCK = threading.Lock()
_AUDIT_EVENT = threading.Event()
_AUDIT_WORKER_STARTED = False
_AUDIT_WORKER_LOCK = threading.Lock()


def _ensure_audit_worker() -> None:
    global _AUDIT_WORKER_STARTED
    if _AUDIT_WORKER_STARTED:
        return
    with _AUDIT_WORKER_LOCK:
        if _AUDIT_WORKER_STARTED:
            return
        thread = threading.Thread(target=_audit_worker, name="fab-audit-log-writer", daemon=True)
        thread.start()
        _AUDIT_WORKER_STARTED = True


def _audit_worker() -> None:
    import logging
    from app.core.db import connect_database
    from app.core.config import settings

    logger = logging.getLogger("fabouanes.audit")

    while True:
        _AUDIT_EVENT.wait(timeout=2.0)
        _AUDIT_EVENT.clear()

        while True:
            batch = []
            with _AUDIT_LOCK:
                while _AUDIT_QUEUE and len(batch) < 50:
                    batch.append(_AUDIT_QUEUE.popleft())

            if not batch:
                break

            try:
                conn = connect_database(settings.database_url)
                try:
                    for row in batch:
                        cur = conn.execute(
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
                        cur.close()
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                logger.exception("Unable to persist audit log batch")


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
    state_user = get_state_value("user")
    actor_user = actor or state_user or {}
    actor_user_id = actor_user.get("id") if isinstance(actor_user, Mapping) else None
    actor_username = actor_user.get("username") if isinstance(actor_user, Mapping) else None
    actor_role = actor_user.get("role") if isinstance(actor_user, Mapping) else None
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
    with _AUDIT_LOCK:
        _AUDIT_QUEUE.append(params)
    _ensure_audit_worker()
    _AUDIT_EVENT.set()


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
    resolved_user_id = user_id
    if resolved_user_id is None:
        user_state = get_state_value("user")
        if isinstance(user_state, dict):
            resolved_user_id = user_state.get("id")
        elif hasattr(user_state, "id"):
            resolved_user_id = getattr(user_state, "id")

    actor_username = "anonymous"
    actor_role = "anonymous"
    if resolved_user_id:
        try:
            from app.repositories.user_repository import get_user_by_id
            user = get_user_by_id(resolved_user_id)
            if user:
                actor_username = user.get("username", "anonymous")
                actor_role = user.get("role", "anonymous")
        except Exception:
            pass
    else:
        user_state = get_state_value("user")
        if user_state:
            if isinstance(user_state, dict):
                actor_username = user_state.get("username", "anonymous")
                actor_role = user_state.get("role", "anonymous")
            else:
                actor_username = getattr(user_state, "username", "anonymous")
                actor_role = getattr(user_state, "role", "anonymous")

    source = get_state_value("audit_source") or "web"

    execute_db(
        """
        INSERT INTO audit_logs
            (action, entity_type, entity_id,
             before_json, actor_user_id, actor_username, actor_role, source, status, created_at)
        VALUES ('delete', %s, %s, %s, %s, %s, %s, %s, 'success', NOW())
        """,
        (
            entity_type,
            str(entity_id),
            json.dumps(snapshot, default=str),
            resolved_user_id,
            actor_username,
            actor_role,
            source,
        ),
    )
