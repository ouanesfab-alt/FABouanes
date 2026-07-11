from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime

from app.core.config import APP_DATA_DIR
from app.core.db_helpers import execute_db
from app.core.request_state import get_state_value

logger = logging.getLogger("fabouanes.activity")
LOG_DIR = APP_DATA_DIR / 'logs'


def write_text_log(filename: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with (LOG_DIR / filename).open('a', encoding='utf-8') as f:
        f.write(f"[{ts}] {message}\n")


def _current_user():
    return get_state_value("user")


def safe_username() -> str:
    try:
        user = _current_user()
        if user:
            return user["username"]
    except Exception:
        pass
    return 'system'


def _request_ip() -> str:
    state_request = get_state_value("request")
    if state_request is None:
        return ""
    forwarded = state_request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",", 1)[0].strip() if forwarded else "") or (
        getattr(getattr(state_request, "client", None), "host", "") or ""
    )


def _json_or_text(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def log_activity(
    action: str,
    entity_type: str = "",
    entity_id: int | None = None,
    details: str = "",
    *,
    old_value=None,
    new_value=None,
) -> None:
    username = safe_username()
    user_id = None
    try:
        user = _current_user()
        if user:
            user_id = int(user["id"])
    except Exception:
        user_id = None
    try:
        execute_db(
            """
            INSERT INTO activity_logs (
                user_id, username, action, entity_type, entity_id, details,
                old_value, new_value, ip_address, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                username,
                action,
                entity_type,
                entity_id,
                details,
                _json_or_text(old_value),
                _json_or_text(new_value),
                _request_ip(),
            ),
        )
    except Exception as exc:
        logger.warning("log_activity DB write failed: %s", exc)
    write_text_log("activity.log", f"{username} | {action} | {entity_type}#{entity_id or '-'} | {details}")


def log_error(exc: Exception, route: str = "") -> None:
    username = safe_username()
    tb = traceback.format_exc()
    current_route = route
    state_request = get_state_value("request")
    if not current_route and state_request is not None:
        current_route = state_request.url.path
    execute_db(
        """
        INSERT INTO error_logs (username, route, error_type, message, traceback, created_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (username, current_route, type(exc).__name__, str(exc), tb),
    )
    write_text_log("errors.log", f"{username} | {current_route} | {type(exc).__name__}: {exc}\n{tb}")
