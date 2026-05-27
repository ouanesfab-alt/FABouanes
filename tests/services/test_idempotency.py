from __future__ import annotations

import os
from unittest.mock import patch, MagicMock
import pytest

from app.core.idempotency import check_idempotency, save_idempotency
from app.core.db_access import execute_db, query_db


@pytest.fixture(autouse=True)
def cleanup_idempotent_requests():
    yield
    # Clean up any test keys from the database table
    try:
        execute_db("DELETE FROM idempotent_requests WHERE key LIKE 'test_key%'")
    except Exception:
        pass


def test_idempotency_no_key():
    """Verify that check_idempotency returns None and save_idempotency returns early when key is None/empty."""
    assert check_idempotency(None) is None
    assert check_idempotency("") is None
    assert check_idempotency("   ") is None
    
    # Should not raise errors
    save_idempotency(None, {"ok": True})
    save_idempotency("", {"ok": True})


def test_idempotency_redis_success():
    """Verify that idempotency works with Redis when Redis is configured and reachable."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = '{"content": {"ok": true}, "status_code": 200}'
    
    with patch("app.core.idempotency._get_redis_client", return_value=mock_redis):
        # 1. Check idempotency (should hit Redis)
        res = check_idempotency("test_key_redis")
        assert res is not None
        assert res["status_code"] == 200
        assert res["content"]["ok"] is True
        mock_redis.get.assert_called_once_with("fabouanes:idempotency:test_key_redis")
        
        # 2. Save idempotency (should save to Redis)
        mock_redis.reset_mock()
        save_idempotency("test_key_redis_save", {"content": {"success": True}, "status_code": 201})
        assert mock_redis.setex.called


def test_idempotency_db_fallback():
    """Verify that when Redis is not available, idempotency falls back to PostgreSQL table."""
    with patch("app.core.idempotency._get_redis_client", return_value=None):
        key = "test_key_db_fallback"
        response = {"content": {"id": 42}, "status_code": 200}
        
        # 1. Save idempotency (should fall back to DB)
        save_idempotency(key, response)
        
        # 2. Verify key was written to database
        row = query_db("SELECT * FROM idempotent_requests WHERE key = %s", (key,), one=True)
        assert row is not None
        assert "response_json" in row
        
        # 3. Check idempotency (should fetch from DB)
        fetched = check_idempotency(key)
        assert fetched is not None
        assert fetched["status_code"] == 200
        assert fetched["content"]["id"] == 42

