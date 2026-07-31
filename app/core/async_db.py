from __future__ import annotations

import asyncio
import os
import threading
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import settings


def get_async_database_url(database_url: str) -> str:
    """Translates standard postgresql URLs to use the asyncpg driver."""
    url = str(database_url or "").strip()
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url

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

    is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")
    default_pool = "5" if is_termux else "10"
    with _ENGINES_LOCK:
        if loop not in _async_engines:
            if "sqlite" in async_database_url:
                engine = create_async_engine(
                    async_database_url,
                    echo=False,
                    future=True,
                    pool_pre_ping=True,
                )
            else:
                connect_kwargs = {}
                if "asyncpg" in async_database_url:
                    connect_kwargs["server_settings"] = {"timezone": "UTC"}

                engine = create_async_engine(
                    async_database_url,
                    echo=False,
                    future=True,
                    pool_pre_ping=True,
                    pool_size=int(os.environ.get("FAB_PG_POOL_SIZE", default_pool)),
                    max_overflow=int(os.environ.get("FAB_PG_POOL_MAX_OVERFLOW", default_pool)),
                    pool_recycle=1800,
                    connect_args=connect_kwargs,
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

async def query_sql_async(statement_str: str, params: dict | tuple = ()):
    """Executes a raw SQL statement asynchronously using SQLAlchemy 2.0 AsyncSession."""
    from sqlalchemy import text
    session_local = get_async_sessionmaker()
    async with session_local() as session:
        result = await session.execute(text(statement_str), params)
        return result.mappings().all()

async def execute_sql_async(statement_str: str, params: dict | tuple = ()):
    """Executes a raw DML statement asynchronously using SQLAlchemy 2.0 AsyncSession."""
    from sqlalchemy import text
    session_local = get_async_sessionmaker()
    async with session_local() as session:
        result = await session.execute(text(statement_str), params)
        await session.commit()
        return result.rowcount

async def async_healthcheck() -> bool:
    """Perform a native async connectivity check to the database using AsyncEngine."""
    try:
        from sqlalchemy import text
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        import logging
        logging.getLogger("fabouanes").error("Async database healthcheck failed: %s", e)
        return False


