from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from flask import g, has_request_context, request

from fabouanes.core.db_access import execute_db, query_db

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
    return value


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(sanitize_payload(row_to_dict(value)), ensure_ascii=False, sort_keys=True)


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
    actor_user = actor or getattr(g, "user", None) or {}
    actor_user_id = actor_user.get("id") if isinstance(actor_user, Mapping) else None
    actor_username = actor_user.get("username") if isinstance(actor_user, Mapping) else None
    actor_role = actor_user.get("role") if isinstance(actor_user, Mapping) else None
    if not actor_username and getattr(g, "user", None):
        actor_username = g.user.get("username")
    if not actor_role and getattr(g, "user", None):
        actor_role = g.user.get("role")
    request_id = getattr(g, "request_id", None)
    request_source = source or getattr(g, "audit_source", None)
    remote_addr = ""
    user_agent = ""
    if has_request_context():
        request_source = request_source or ("api" if request.path.startswith("/api/") else "web")
        remote_addr = request.remote_addr or ""
        user_agent = request.headers.get("User-Agent", "")[:500]
    else:
        request_source = request_source or "system"
    execute_db(
        """
        INSERT INTO audit_logs (
            actor_user_id,
            actor_username,
            actor_role,
            source,
            action,
            entity_type,
            entity_id,
            status,
            ip_address,
            user_agent,
            request_id,
            before_json,
            after_json,
            meta_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
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
        ),
    )


def list_audit_logs(filters: Mapping[str, Any] | None = None, *, limit: int = 200):
    filters = filters or {}
    where: list[str] = []
    params: list[Any] = []
    if filters.get("date_from"):
        where.append("substr(created_at, 1, 10) >= ?")
        params.append(str(filters["date_from"]))
    if filters.get("date_to"):
        where.append("substr(created_at, 1, 10) <= ?")
        params.append(str(filters["date_to"]))
    if filters.get("actor"):
        where.append("lower(actor_username) LIKE lower(?)")
        params.append(f"%{filters['actor']}%")
    if filters.get("action"):
        where.append("lower(action) LIKE lower(?)")
        params.append(f"%{filters['action']}%")
    if filters.get("entity_type"):
        where.append("lower(entity_type) LIKE lower(?)")
        params.append(f"%{filters['entity_type']}%")
    if filters.get("status"):
        where.append("status = ?")
        params.append(str(filters["status"]))
    query = """
        SELECT *
        FROM audit_logs
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT ?"
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
