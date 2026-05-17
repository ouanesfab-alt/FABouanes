"""
Responsibility: Entry point for database connections, engine management, and high-level status.
"""
from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.db_compat import CompatConnection, adapt_query, split_sql_script
from app.core.db_sqlite import get_sqlite_pool

_ENGINES: dict[str, Engine] = {}
_ENGINE_LOCK = Lock()


def _env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or default)
    except Exception:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def sqlalchemy_database_url(database_url: str) -> str:
    url = str(database_url or "").strip()
    if url.startswith("postgresql://"):
        return "postgresql+pg8000://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+pg8000://" + url[len("postgres://") :]
    return url


def create_database_engine(database_url: str) -> Engine:
    engine_url = sqlalchemy_database_url(database_url)
    if not database_url.lower().startswith("postgres"):
        return create_engine(engine_url, future=True)
    return create_engine(
        engine_url,
        future=True,
        pool_pre_ping=True,
        pool_size=_env_int("FAB_PG_POOL_SIZE", 10, 1, 200),
        max_overflow=_env_int("FAB_PG_POOL_MAX_OVERFLOW", 10, 0, 500),
        pool_timeout=_env_int("FAB_PG_POOL_TIMEOUT", 30, 1, 300),
        pool_recycle=_env_int("FAB_PG_POOL_RECYCLE_SECONDS", 1800, 60, 86400),
    )


def get_database_engine(database_url: str) -> Engine:
    raw_url = str(database_url or "").strip()
    with _ENGINE_LOCK:
        engine = _ENGINES.get(raw_url)
        if engine is None:
            engine = create_database_engine(raw_url)
            _ENGINES[raw_url] = engine
        return engine


def connect_database(database_url: str, sqlite_path: str | Path | None = None) -> CompatConnection:
    raw_url = str(database_url or "").strip()
    if raw_url.lower().startswith("postgres"):
        engine = get_database_engine(raw_url)
        return CompatConnection(
            engine.raw_connection(),
            "postgres",
            reconnect=lambda: engine.raw_connection(),
        )
    
    if not raw_url.lower().startswith("sqlite"):
        raise RuntimeError(f"DATABASE_URL non supportee: {raw_url}")
    
    resolved_sqlite_path = _sqlite_path_from_url(raw_url, sqlite_path)
    Path(resolved_sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    pool = get_sqlite_pool(str(resolved_sqlite_path))
    conn = pool.get()
    return CompatConnection(
        conn,
        "sqlite",
        on_close=lambda c: pool.put(c),
    )


def postgres_pool_status(database_url: str) -> dict[str, int | str]:
    if not str(database_url or "").lower().startswith("postgres"):
        return {"engine": "sqlite"}
    pool = get_database_engine(database_url).pool
    status: dict[str, int | str] = {"engine": "postgres"}
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


def _sqlite_path_from_url(database_url: str, sqlite_path: str | Path | None) -> str | Path:
    raw = str(database_url or "").strip()
    if raw.lower().startswith("sqlite:///"):
        parsed = urlparse(raw)
        if parsed.netloc:
            return Path(f"//{parsed.netloc}{unquote(parsed.path)}")
        path = unquote(parsed.path)
        if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return Path(path)
    if sqlite_path is not None:
        return sqlite_path
    data_dir = os.environ.get("FAB_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "database.db"
    return Path.cwd() / "database.db"


def list_columns(conn: CompatConnection, table: str) -> set[str]:
    if conn.dialect == "sqlite":
        cur = conn.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        cur.close()
        return {row[1] for row in rows}
    cur = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return {row["column_name"] for row in rows}
