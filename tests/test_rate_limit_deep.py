"""Tests unitaires pour app/core/rate_limit.py et rate_limit_store.py (Couverture > 90%)."""
from __future__ import annotations

from unittest import mock
import pytest
from starlette.responses import JSONResponse

from app.core.rate_limit_store import _InMemoryRateLimitStore, RateLimitStore

from app.core.rate_limit import limiter, rate_limit_exceeded_handler



def test_in_memory_rate_limit_store_lifecycle():
    store = _InMemoryRateLimitStore()
    key = "user_123"

    # Consume attempts up to limit
    assert store.consume(key, limit=2, window_seconds=60) is True
    assert store.consume(key, limit=2, window_seconds=60) is True
    assert store.consume(key, limit=2, window_seconds=60) is False  # limit reached

    # Record failure
    store.record_failure(key)
    assert store.is_locked_out(key, max_attempts=2, window_s=60, lockout_s=10) is True

    # Clear
    store.clear(key)
    assert store.is_locked_out(key, max_attempts=2, window_s=60, lockout_s=10) is False
    assert store.consume(key, limit=2, window_seconds=60) is True


def test_is_rate_limited_in_memory_wrapper():
    key = "ip_456"
    RateLimitStore.clear(key)

    consumed = RateLimitStore.consume(key, limit=1, window_seconds=60)
    assert consumed is True

    consumed2 = RateLimitStore.consume(key, limit=1, window_seconds=60)
    assert consumed2 is False


def test_dummy_limiter():
    assert limiter is not None
    assert hasattr(limiter, "limit") or hasattr(limiter, "enabled")




@pytest.mark.asyncio
async def test_rate_limit_exceeded_handler():
    req = mock.MagicMock()
    exc = mock.MagicMock()
    resp = await rate_limit_exceeded_handler(req, exc)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 429
