from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable


def async_compat(func: Callable[..., Any]) -> Callable[..., Any]:
    """Allows an async function to be called synchronously if no event loop is running."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            return func(*args, **kwargs)
        else:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


def db_task_compat(func: Callable[..., Any]) -> Any:
    """
    Decorator for our newly migrated async repositories to keep full compatibility
    with callers calling it asynchronously (via await func(...) or await func.async_(...))
    or synchronously (via func(...) in a sync context).
    """
    wrapper: Any = async_compat(func)
    wrapper.async_ = wrapper
    wrapper.sync = wrapper
    return wrapper
