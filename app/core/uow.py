# -*- coding: utf-8 -*-
"""
Unit of Work (UoW) pattern implementation for FABouanes.
Manages transactional boundaries, automatic commit/rollback, and eliminates session leaks.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_sessionmaker

logger = logging.getLogger("fabouanes.uow")

_post_commit_hooks: contextvars.ContextVar[list[Callable[..., Any]] | None] = contextvars.ContextVar(
    "post_commit_hooks", default=None
)


def register_post_commit_hook(callback: Callable[..., Any]) -> None:
    """Enregistre une action à exécuter uniquement après le succès de uow.commit()."""
    hooks = _post_commit_hooks.get()
    if hooks is not None:
        hooks.append(callback)
    else:
        _dispatch_hook(callback)


def _dispatch_hook(callback: Callable[..., Any]) -> None:
    try:
        if asyncio.iscoroutinefunction(callback):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(callback())
            except RuntimeError:
                try:
                    asyncio.run(callback())
                except Exception:
                    pass
        else:
            res = callback()
            if asyncio.iscoroutine(res):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(res)
                except RuntimeError:
                    try:
                        asyncio.run(res)
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("Error executing post-commit action: %s", exc)


async def execute_post_commit_hooks() -> None:
    """Exécute tous les hooks enregistrés pour le cycle UoW courant."""
    hooks = _post_commit_hooks.get()
    if not hooks:
        return
    current = list(hooks)
    hooks.clear()
    for cb in current:
        try:
            if asyncio.iscoroutinefunction(cb):
                await cb()
            else:
                res = cb()
                if asyncio.iscoroutine(res):
                    await res
        except Exception as exc:
            logger.warning("Post-commit action failed: %s", exc)


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
    - Triggers registered post-commit actions only after successful commit.
    """
    if db is not None:
        yield db
        return

    factory = session_factory or get_async_sessionmaker
    session_maker = factory()
    session_candidate = session_maker() if callable(session_maker) else session_maker

    token = None
    if _post_commit_hooks.get() is None:
        token = _post_commit_hooks.set([])

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
                await execute_post_commit_hooks()
            except Exception:
                hooks = _post_commit_hooks.get()
                if hooks:
                    hooks.clear()
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
                if token is not None:
                    _post_commit_hooks.reset(token)
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
        await execute_post_commit_hooks()
    except Exception:
        hooks = _post_commit_hooks.get()
        if hooks:
            hooks.clear()
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
        if token is not None:
            _post_commit_hooks.reset(token)
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
