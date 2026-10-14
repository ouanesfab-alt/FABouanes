"""Tests de couverture ciblés — Lot 4.

Couvre: rate_limit_store.py (_DbRateLimitStore, _RedisRateLimitStore fallback), rate_limit.py (DummyLimiter),
        lifespan.py error handlers, permissions.py error responses
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── rate_limit.py (DummyLimiter) ───────────────────────────────────


def test_dummy_limiter_fallback():
    """Test rate_limit module fallback DummyLimiter when slowapi is not present."""
    import sys
    import importlib

    with patch.dict(sys.modules, {"slowapi": None}):
        import app.core.rate_limit as rl
        importlib.reload(rl)

        decorator = rl.limiter.limit("100/minute")

        def dummy_func(a, b):
            return a + b

        wrapped = decorator(dummy_func)
        assert wrapped(2, 3) == 5

    # Reload module normally to restore state
    import app.core.rate_limit as rl
    importlib.reload(rl)



# ── rate_limit_store.py (_DbRateLimitStore & _RedisRateLimitStore) ──


def test_db_rate_limit_store_methods():
    """Test _DbRateLimitStore with mocked db calls."""
    from app.core.rate_limit_store import _DbRateLimitStore

    store = _DbRateLimitStore()

    with patch("app.core.db_helpers.execute_db") as mock_exec, \
         patch("app.core.db_helpers.query_db") as mock_query:

        mock_query.return_value = {"cnt": 2}
        assert store.consume("test_key", limit=5, window_seconds=60.0) is True

        mock_query.return_value = {"cnt": 10}
        assert store.consume("test_key", limit=5, window_seconds=60.0) is False

        store.record_failure("test_user")
        assert mock_exec.called

        mock_query.return_value = [{"hit_epoch": 1000.0}]
        with patch("time.time", return_value=1005.0):
            res = store.is_locked_out("test_user", max_attempts=5, window_s=60.0, lockout_s=30.0)
            assert res is False

        store.clear("test_key")
        store.clear_user("alice")
        store.clear_all()


def test_db_rate_limit_store_clear_user_exception_fallback():
    """_DbRateLimitStore.clear_user falls back to memory store on DB exception."""
    from app.core.rate_limit_store import _DbRateLimitStore, _fallback_in_memory

    store = _DbRateLimitStore()
    _fallback_in_memory.consume("login:fail_user:ip", 10, 60.0)

    with patch("app.core.db_helpers.execute_db", side_effect=RuntimeError("DB Error")):
        store.clear_user("fail_user")
        # Should call fallback store without raising exception
        assert "login:fail_user:ip" not in _fallback_in_memory._attempts


def test_db_rate_limit_store_clear_all_exception_handling():
    """_DbRateLimitStore.clear_all handles exception gracefully."""
    from app.core.rate_limit_store import _DbRateLimitStore

    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db", side_effect=RuntimeError("DB Error")):
        store.clear_all()  # should not raise


def test_redis_rate_limit_store_fallback_on_error():
    """_RedisRateLimitStore falls back to in-memory store when Redis fails."""
    from app.core.rate_limit_store import _RedisRateLimitStore

    with patch("redis.from_url") as mock_redis_factory:
        mock_client = MagicMock()
        mock_client.pipeline.side_effect = RuntimeError("Redis connection lost")
        mock_client.delete.side_effect = RuntimeError("Redis connection lost")
        mock_client.keys.side_effect = RuntimeError("Redis connection lost")
        mock_redis_factory.return_value = mock_client

        store = _RedisRateLimitStore("redis://localhost:6379/0")

        # All operations should fall back to memory store without raising exception
        assert store.consume("r_key", 5, 60.0) is True
        store.record_failure("r_user")
        assert store.is_locked_out("r_user", 5, 60.0, 30.0) is False
        store.clear("r_key")
        store.clear_user("r_user")
        store.clear_all()


def test_redis_rate_limit_store_normal_operations():
    """_RedisRateLimitStore normal pipeline execution."""
    from app.core.rate_limit_store import _RedisRateLimitStore

    with patch("redis.from_url") as mock_redis_factory:
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None, 2, None, None]  # 2 hits
        mock_client.pipeline.return_value = mock_pipe
        mock_client.zrangebyscore.return_value = ["100.0", "101.0"]
        mock_client.keys.return_value = ["rate_limit:hits:test"]
        mock_redis_factory.return_value = mock_client

        store = _RedisRateLimitStore("redis://localhost:6379/0")

        assert store.consume("key1", limit=5, window_seconds=60.0) is True
        store.record_failure("user1")
        assert store.is_locked_out("user1", max_attempts=5, window_s=60.0, lockout_s=30.0) is False
        store.clear("key1")
        store.clear_user("user1")
        store.clear_all()


# ── permissions.py (92% → target ~96%) ──────────────────────────────


def test_permission_denied_response_api():
    """permission_denied_response returns JSON for API path."""
    from app.core.permissions import permission_denied_response

    mock_req = MagicMock()
    mock_req.url.path = "/api/v1/resource"

    with patch("app.core.permissions.get_state_value") as mock_state:
        def state_side_effect(key):
            if key == "request":
                return mock_req
            if key == "user":
                return {"id": 1, "username": "admin"}
            return None

        mock_state.side_effect = state_side_effect
        with patch("app.core.permissions._audit_permission_denied"):
            resp = permission_denied_response("admin_access")
            assert resp.status_code == 403
            assert b"forbidden" in resp.body or b"refusee" in resp.body



# ── lifespan.py exception branches ─────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_context_manager_startup_shutdown():
    """Test lifespan startup and shutdown with mocked sub-systems."""
    from app.core.lifespan import lifespan

    app = MagicMock()

    with patch("app.core.lifespan.validate_single_worker_runtime"), \
         patch("app.core.lifespan.ensure_runtime_dirs"), \
         patch("app.core.lifespan.configure_logging"), \
         patch("app.core.lifespan.start_audit_worker"), \
         patch("app.core.lifespan.stop_audit_worker"), \
         patch("app.core.lifespan.bootstrap_and_migrate"), \
         patch("app.services.backup_service.start_background_services"), \
         patch("app.services.backup_service.shutdown_background_services"), \
         patch("app.core.lifespan.get_enabled_modules", return_value=[]):

        async with lifespan(app):
            pass
