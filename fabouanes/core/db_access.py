from __future__ import annotations

from contextlib import contextmanager

from flask import g
from fabouanes.config import DATABASE_URL, APP_DATA_DIR
from fabouanes.db import connect_database

DB_PATH = APP_DATA_DIR / "database.db"

def get_db():
    if "db" not in g:
        g.db = connect_database(DATABASE_URL, DB_PATH)
    return g.db

def query_db(query: str, params: tuple = (), one: bool = False):
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows

def execute_db(query: str, params: tuple = ()) -> int:
    db = get_db()
    cur = db.execute(query, params)
    if int(getattr(g, "_db_tx_depth", 0) or 0) == 0:
        db.commit()
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
