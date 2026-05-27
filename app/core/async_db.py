from __future__ import annotations

import os
import asyncio
import threading
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
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

_ENGINES: dict[int, AsyncEngine] = {}
_ENGINES_LOCK = threading.Lock()

def get_async_engine() -> AsyncEngine:
    """Returns a thread-safe and loop-safe AsyncEngine instance."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    loop_id = id(loop) if loop is not None else 0
    
    with _ENGINES_LOCK:
        if loop_id not in _ENGINES:
            _ENGINES[loop_id] = create_async_engine(
                async_database_url,
                echo=False,
                future=True,
                pool_pre_ping=True,
                pool_size=int(os.environ.get("FAB_PG_POOL_SIZE", "10")),
                max_overflow=int(os.environ.get("FAB_PG_POOL_MAX_OVERFLOW", "10")),
            )
        return _ENGINES[loop_id]

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

