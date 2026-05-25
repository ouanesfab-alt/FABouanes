from __future__ import annotations

from contextvars import ContextVar, Token
from types import SimpleNamespace
from typing import Any


_request_state: ContextVar[SimpleNamespace | None] = ContextVar("fab_request_state", default=None)


def push_request_state(**values: Any) -> Token:
    state = SimpleNamespace(**values)
    return _request_state.set(state)


def get_request_state() -> SimpleNamespace | None:
    return _request_state.get()


def ensure_request_state() -> SimpleNamespace:
    state = get_request_state()
    if state is None:
        state = SimpleNamespace()
        _request_state.set(state)
    return state


def set_state_value(name: str, value: Any) -> None:
    setattr(ensure_request_state(), name, value)


def get_state_value(name: str, default: Any = None) -> Any:
    state = get_request_state()
    if state is None:
        return default
    return getattr(state, name, default)


def reset_request_state(token: Token) -> None:
    _request_state.reset(token)


def get_current_request():
    """Reads from the ContextVar and raises a clear error if called outside a request context.

    Note: This is part of the new dependency injection way. The global ContextVar approach is legacy.
    """
    from fastapi import Request
    state = get_request_state()
    if state is None or not hasattr(state, "request") or state.request is None:
        raise RuntimeError("No active request context found.")
    return state.request
