from __future__ import annotations

import os
import asyncio
import threading
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlmodel import SQLModel

from app.core.config import settings

def get_async_database_url(database_url: str) -> str:
    """Translates database URLs to use the aiosqlite driver for SQLite.

    Note: PostgreSQL URLs are not supported in this version and will fall back
    to the local SQLite database with an explicit warning.
    """
    url = str(database_url or "").strip()
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://"):]
    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        import logging as _logging
        data_dir = settings.app_data_dir
        db_path = (data_dir / "fabouanes.db").resolve().as_posix()
        _logging.getLogger("fabouanes").warning(
            "[ASYNC_DB] URL PostgreSQL détectée dans get_async_database_url mais le support "
            "asynchrone PostgreSQL (asyncpg) n'est pas activé. Retour sur SQLite : %s.",
            db_path,
        )
        return f"sqlite+aiosqlite:///{db_path}"
    return url if url else f"sqlite+aiosqlite:///{(settings.app_data_dir / 'fabouanes.db').resolve().as_posix()}"

async_database_url = get_async_database_url(settings.database_url)

_async_engines: dict[asyncio.AbstractEventLoop | str, AsyncEngine] = {}
_ENGINES_LOCK = threading.Lock()

def get_async_engine() -> AsyncEngine:
    """Returns an AsyncEngine instance specific to the current event loop."""
    global _async_engines
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = "default"

    with _ENGINES_LOCK:
        if loop not in _async_engines:
            url = get_async_database_url(settings.database_url)
            if "sqlite" in url:
                engine = create_async_engine(
                    url,
                    echo=False,
                    future=True,
                    connect_args={"check_same_thread": False},
                )
                from sqlalchemy import event
                from app.core.db_helpers.manager import _register_sqlite_custom_functions
                @event.listens_for(engine.sync_engine, "connect")
                def set_sqlite_pragmas(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute("PRAGMA journal_mode = WAL;")
                        cursor.execute("PRAGMA busy_timeout = 30000;")
                        cursor.execute("PRAGMA foreign_keys = ON;")
                        cursor.execute("PRAGMA synchronous = NORMAL;")
                    except Exception:
                        pass
                    finally:
                        cursor.close()
                    _register_sqlite_custom_functions(dbapi_connection)
            else:
                engine = create_async_engine(
                    url,
                    echo=False,
                    future=True,
                    pool_pre_ping=True,
                    pool_size=int(os.environ.get("FAB_PG_POOL_SIZE", "10")),
                    max_overflow=int(os.environ.get("FAB_PG_POOL_MAX_OVERFLOW", "10")),
                    pool_recycle=1800,
                )
            _async_engines[loop] = engine
        return _async_engines[loop]

async def close_async_engine() -> None:
    """Properly closes and disposes of all global AsyncEngines."""
    global _async_engines
    with _ENGINES_LOCK:
        for engine in _async_engines.values():
            await engine.dispose()
        _async_engines.clear()


def get_async_sessionmaker():
    """Returns a sessionmaker bound to the loop-safe AsyncEngine."""
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

class LoopBoundSessionLocal:
    """Dynamic sessionmaker that forwards calls to the current loop-safe sessionmaker."""
    def __call__(self, *args, **kwargs):
        return get_async_sessionmaker()(*args, **kwargs)

    def configure(self, *args, **kwargs):
        return get_async_sessionmaker().configure(*args, **kwargs)

AsyncSessionLocal = LoopBoundSessionLocal()

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:

    """Dependency injection session getter for FastAPI endpoints."""
    session_local = get_async_sessionmaker()
    async with session_local() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_db_and_tables():
    """Bootstraps/Creates database tables defined via SQLModel."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


from contextlib import asynccontextmanager

@asynccontextmanager
async def ensure_transaction(db: AsyncSession | None = None):
    """Context manager that guarantees an active transaction.

    If ``db`` is provided and already inside a transaction, yields it as-is.
    Otherwise creates a new session with an explicit ``begin()`` so the caller
    always gets a properly managed transaction that will commit on success and
    rollback on failure.

    Usage::

        async with ensure_transaction(db) as session:
            session.add(obj)
            await session.flush()
        # auto-commit on exit, auto-rollback on exception
    """
    if db is not None:
        yield db
    else:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                yield session

