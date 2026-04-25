from __future__ import annotations

from datetime import datetime
from flask import g
from fabouanes.core.db_access import execute_db
from fabouanes.config import APP_DATA_DIR

LOG_DIR = APP_DATA_DIR / 'logs'

def now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def write_text_log(filename: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / filename).open('a', encoding='utf-8') as f:
        f.write(f"[{now_str()}] {message}\n")

def safe_username() -> str:
    try:
        if getattr(g, 'user', None):
            return g.user['username']
    except Exception:
        pass
    return 'system'

def log_activity(action: str, entity_type: str = '', entity_id: int | None = None, details: str = '') -> None:
    username = safe_username()
    execute_db('INSERT INTO activity_logs (username, action, entity_type, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)', (username, action, entity_type, entity_id, details))
    write_text_log('activity.log', f"{username} | {action} | {entity_type}#{entity_id or '-'} | {details}")
