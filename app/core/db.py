"""
Responsibility: Entry point for database connections, engine management, and high-level status.
"""
from __future__ import annotations

import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.db_compat import CompatConnection, adapt_query, split_sql_script

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


def connect_database(database_url: str) -> CompatConnection:
    raw_url = str(database_url or "").strip()
    try:
        engine = get_database_engine(raw_url)
        conn = engine.raw_connection()
    except Exception as e:
        err_msg = str(e).lower()
        # 3d000 is the SQLSTATE for database_does_not_exist
        if "does not exist" in err_msg or "3d000" in err_msg:
            from urllib.parse import urlparse
            from sqlalchemy import text
            parsed = urlparse(raw_url)
            database = parsed.path.lstrip("/")
            # Use 'postgres' default database to run CREATE DATABASE
            port_part = f":{parsed.port}" if parsed.port else ""
            pass_part = f":{parsed.password}" if parsed.password else ""
            user_part = f"{parsed.username}{pass_part}@" if parsed.username else ""
            postgres_url = f"{parsed.scheme}://{user_part}{parsed.hostname}{port_part}/postgres"
            
            # Create transient autocommit engine to execute CREATE DATABASE
            pg_engine = create_engine(sqlalchemy_database_url(postgres_url), isolation_level="AUTOCOMMIT", future=True)
            with pg_engine.connect() as pg_conn:
                pg_conn.execute(text(f'CREATE DATABASE "{database}"'))
            pg_engine.dispose()
            
            # Retry connection to the newly created database
            engine = get_database_engine(raw_url)
            conn = engine.raw_connection()
        else:
            raise e

    return CompatConnection(
        conn,
        "postgres",
        reconnect=lambda: engine.raw_connection(),
    )


def postgres_pool_status(database_url: str) -> dict[str, int | str]:
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


def list_columns(conn: CompatConnection, table: str) -> set[str]:
    cur = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return {row["column_name"] for row in rows}
