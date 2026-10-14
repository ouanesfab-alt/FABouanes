# -*- coding: utf-8 -*-
"""
Unit of Work (UoW) pattern implementation for FABouanes.
Manages transactional boundaries, automatic commit/rollback, and eliminates session leaks.
"""
from __future__ import annotations

import asyncio
import functools
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker


@asynccontextmanager
async def unit_of_work(
    db: AsyncSession | None = None,
    *,
    auto_commit: bool = True,
    session_factory: Callable[..., Any] | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager providing an AsyncSession with Unit of Work guarantees:
    - If `db` is already provided (e.g. from FastAPI Depends(get_async_session)),
      yields `db` directly. The outer caller retains ownership of the session and transaction.
    - If `db` is None, opens a new loop-bound AsyncSession. If no exception occurs and `auto_commit`
      is True, commits all pending changes. If an exception occurs, executes a rollback and re-raises.
      In all cases, closes the newly created session.
    """
    if db is not None:
        yield db
        return

    factory = session_factory or get_async_sessionmaker
    session_maker = factory()
    session_candidate = session_maker() if callable(session_maker) else session_maker

    if hasattr(session_candidate, "__aenter__"):
        async with session_candidate as session:
            try:
                yield session
                if auto_commit:
                    commit_fn = getattr(session, "commit", None)
                    if commit_fn and callable(commit_fn):
                        res = commit_fn()
                        if asyncio.iscoroutine(res):
                            await res
            except Exception:
                rollback_fn = getattr(session, "rollback", None)
                if rollback_fn and callable(rollback_fn):
                    try:
                        res = rollback_fn()
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass
                raise
        return

    session = session_candidate
    try:
        yield session
        if auto_commit:
            commit_fn = getattr(session, "commit", None)
            if commit_fn and callable(commit_fn):
                res = commit_fn()
                if asyncio.iscoroutine(res):
                    await res
    except Exception:
        rollback_fn = getattr(session, "rollback", None)
        if rollback_fn and callable(rollback_fn):
            try:
                res = rollback_fn()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        raise
    finally:
        close_fn = getattr(session, "close", None)
        if close_fn and callable(close_fn):
            try:
                res = close_fn()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass


def with_uow(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator for service/repository functions accepting `db: AsyncSession | None = None`.
    Ensures that if `db` is None, a new unit_of_work session is created, passed,
    and committed upon successful completion.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        db = kwargs.get("db")
        if db is not None:
            return await func(*args, **kwargs)
        async with unit_of_work() as session:
            kwargs["db"] = session
            return await func(*args, **kwargs)

    return wrapper
