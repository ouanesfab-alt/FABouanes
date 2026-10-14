"""
test_coverage_boost_lot37.py
Targets:
  - rate_limit_store.py: Redis rate limit lockout exponential backoff, backend selection logic (lines 252-255, 284-290)
  - exception_handlers.py: exception handlers custom error structures (lines 112, 130-131, 157-158, 187-188)
  - permissions.py: user with unknown role or empty permissions (lines 176, 188-189)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. rate_limit_store.py — Redis exponential backoff & backend selection
# ============================================================

def test_redis_rate_limit_store_is_locked_out_exponential():
    """Lines 252-255: Redis Rate Limit lockout exponential calculation."""
    from app.core.rate_limit_store import _RedisRateLimitStore
    import time

    mock_client = MagicMock()
    now = time.time()
    # 5 failures in redis
    mock_client.zrangebyscore.return_value = [str(now - i).encode() for i in range(5)]

    store = _RedisRateLimitStore("redis://localhost:6379/0")
    store.client = mock_client

    is_locked = store.is_locked_out("user1", max_attempts=3, window_s=600.0, lockout_s=30.0)
    assert is_locked is True


def test_rate_limit_backend_selection_env_vars():
    """Lines 284-290: RateLimitStore backend selection based on env vars."""
    import importlib
    import app.core.rate_limit_store as rls

    with patch.dict("os.environ", {"FAB_RATE_LIMIT_BACKEND": "db"}):
        importlib.reload(rls)
        assert isinstance(rls.RateLimitStore, rls._DbRateLimitStore)

    with patch.dict("os.environ", {"FAB_RATE_LIMIT_BACKEND": "memory", "REDIS_URL": ""}):
        importlib.reload(rls)
        assert isinstance(rls.RateLimitStore, rls._InMemoryRateLimitStore)


# ============================================================
# 2. exception_handlers.py — validation and HTTP error formatters
# ============================================================

@pytest.mark.asyncio
async def test_exception_handlers_custom_errors():
    """Lines 112, 130-131, 157-158, 187-188: custom exception handler HTML responses."""
    from app.core.exception_handlers import (
        http_exception_handler,
        unhandled_exception_handler,
        validation_error_handler,
    )
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from starlette.requests import Request

    html_scope = {
        "type": "http",
        "method": "GET",
        "path": "/web/test",
        "headers": [(b"accept", b"text/html")],
        "query_string": b"",
    }
    req = Request(html_scope)

    mock_templates = MagicMock()
    mock_templates.TemplateResponse.return_value = MagicMock(status_code=400)

    with patch("app.web.deps.templates", mock_templates), \
         patch("app.web.deps.template_context", return_value={}):

        # Line 112: HTTP exception with dict detail on HTML request
        http_err = HTTPException(status_code=400, detail={"message": "Invalid param"})
        await http_exception_handler(req, http_err)

        # Line 130-131: ValueError on HTML request
        val_err = ValueError("Invalid input value")
        await unhandled_exception_handler(req, val_err)

        # Line 157-158: Generic unhandled exception on HTML request
        gen_err = Exception("foreign key constraint violated")
        await unhandled_exception_handler(req, gen_err)

        # Line 187-188: RequestValidationError on HTML request
        req_val_err = RequestValidationError([{"loc": ("body", "name"), "msg": "required"}])
        await validation_error_handler(req, req_val_err)


# ============================================================
# 3. permissions.py — permission checks with edge role values
# ============================================================

def test_permissions_unknown_role():
    """Lines 176, 188-189: permission checks for user with unknown or None role."""
    from app.core.permissions import has_permission, require_permission

    user_unknown = {"role": "guest_role", "custom_permissions_json": "[]"}
    assert has_permission(user_unknown, "sales.read") is False

    user_none = {"role": None}
    assert has_permission(user_none, "sales.read") is False

    with pytest.raises(Exception):
        require_permission(user_unknown, "sales.write")
