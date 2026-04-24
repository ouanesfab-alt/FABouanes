from __future__ import annotations

import os
from contextlib import contextmanager

from fabouanes.fastapi_compat import g
from fabouanes.config import DATABASE_URL, APP_DATA_DIR
from fabouanes.db import connect_database
from fabouanes.postgres_support import SQLITE_IMPORT_FILE_NAME

SQLITE_IMPORT_PATH_HINT = APP_DATA_DIR / SQLITE_IMPORT_FILE_NAME

def get_db():
    if "db" not in g:
        g.db = connect_database(DATABASE_URL, SQLITE_IMPORT_PATH_HINT)
    return g.db

def query_db(query: str, params: tuple = (), one: bool = False):
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def default_page_size() -> int:
    raw = (os.environ.get("WEB_PAGE_SIZE", "") or "").strip()
    try:
        value = int(raw) if raw else 100
    except Exception:
        value = 100
    return max(10, min(value, 500))


def max_page_size() -> int:
    raw = (os.environ.get("WEB_MAX_PAGE_SIZE", "") or "").strip()
    try:
        value = int(raw) if raw else 500
    except Exception:
        value = 500
    return max(10, min(value, 2000))


def normalize_pagination(page: int | None, page_size: int | None) -> tuple[int, int, int]:
    resolved_page = int(page or 1)
    if resolved_page < 1:
        resolved_page = 1
    resolved_size = int(page_size or default_page_size())
    resolved_size = max(1, min(resolved_size, max_page_size()))
    return resolved_page, resolved_size, (resolved_page - 1) * resolved_size


def paged_query(
    query: str,
    params: tuple = (),
    *,
    page: int,
    page_size: int,
    count_query: str | None = None,
    count_params: tuple | None = None,
):
    safe_page, safe_page_size, offset = normalize_pagination(page, page_size)
    resolved_count_query = count_query or f"SELECT COUNT(*) AS c FROM ({query}) paged_src"
    resolved_count_params = count_params if count_params is not None else params
    count_row = query_db(resolved_count_query, resolved_count_params, one=True)
    rows = query_db(f"{query} LIMIT ? OFFSET ?", params + (safe_page_size, offset))
    total = int((count_row["c"] if count_row else 0) or 0)
    total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 1
    return rows, {
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": safe_page > 1,
        "has_next": safe_page < total_pages,
    }

def execute_db(query: str, params: tuple = ()) -> int:
    db = get_db()
    cur = db.execute(query, params)
    if int(getattr(g, "_db_tx_depth", 0) or 0) == 0:
        db.commit()
    try:
        from fabouanes.core.perf_cache import mark_cache_dirty

        mark_cache_dirty()
    except Exception:
        pass
    last_id = cur.lastrowid
    cur.close()
    return int(last_id or 0)

@contextmanager
def db_transaction():
    db = get_db()
    previous_depth = int(getattr(g, "_db_tx_depth", 0) or 0)
    g._db_tx_depth = previous_depth + 1
    try:
        yield db
    except Exception:
        if previous_depth == 0:
            try:
                db.rollback()
            except Exception:
                pass
        raise
    else:
        if previous_depth == 0:
            db.commit()
    finally:
        g._db_tx_depth = previous_depth

def get_setting(key: str, default: str = '') -> str:
    try:
        row = query_db('SELECT value FROM app_settings WHERE key = ?', (key,), one=True)
        return row['value'] if row and row['value'] is not None else default
    except Exception:
        return default

def set_setting(key: str, value: str) -> None:
    execute_db('INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP', (key, value))
