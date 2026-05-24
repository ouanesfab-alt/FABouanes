from __future__ import annotations

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
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

async_engine = create_async_engine(
    async_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=int(os.environ.get("FAB_PG_POOL_SIZE", "10")),
    max_overflow=int(os.environ.get("FAB_PG_POOL_MAX_OVERFLOW", "10")),
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection session getter for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_db_and_tables():
    """Bootstraps/Creates database tables defined via SQLModel."""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
