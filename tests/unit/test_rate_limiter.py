from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from app.core.rate_limit_store import _InMemoryRateLimitStore, _DbRateLimitStore


class TestInMemoryRateLimitStore:
    def test_consume_under_limit(self):
        store = _InMemoryRateLimitStore()
        # Consume 3 hits, limit is 3, window is 10s
        assert store.consume("test_key", limit=3, window_seconds=10.0) is True
        assert store.consume("test_key", limit=3, window_seconds=10.0) is True
        assert store.consume("test_key", limit=3, window_seconds=10.0) is True
        # 4th hit should be blocked
        assert store.consume("test_key", limit=3, window_seconds=10.0) is False

    def test_consume_window_sliding(self):
        store = _InMemoryRateLimitStore()
        
        # We can mock time.monotonic to control the time flow
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            assert store.consume("test_key", limit=2, window_seconds=10.0) is True
            assert store.consume("test_key", limit=2, window_seconds=10.0) is True
            assert store.consume("test_key", limit=2, window_seconds=10.0) is False
            
            # Move time forward by 11 seconds (outside the 10s window)
            mock_time.return_value = 111.0
            # Now we should be able to consume again
            assert store.consume("test_key", limit=2, window_seconds=10.0) is True

    def test_record_failure_and_lockout(self):
        store = _InMemoryRateLimitStore()
        key = "test_user_ip"
        
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            
            # No failures yet, should not be locked out
            assert store.is_locked_out(key, max_attempts=3, window_s=60, lockout_s=10) is False
            
            # Record 3 failures
            store.record_failure(key)
            store.record_failure(key)
            store.record_failure(key)
            
            # Now should be locked out
            assert store.is_locked_out(key, max_attempts=3, window_s=60, lockout_s=10) is True
            
            # Lockout time should have exponential backoff: lockout_s * 2^0 = 10s.
            # So until 110.0. Let's check at 105.0 (still locked out)
            mock_time.return_value = 105.0
            assert store.is_locked_out(key, max_attempts=3, window_s=60, lockout_s=10) is True
            
            # At 111.0, lockout should be expired
            mock_time.return_value = 111.0
            assert store.is_locked_out(key, max_attempts=3, window_s=60, lockout_s=10) is False

    def test_clear(self):
        store = _InMemoryRateLimitStore()
        store.consume("key1", limit=1, window_seconds=10.0)
        assert store.consume("key1", limit=1, window_seconds=10.0) is False
        
        store.clear("key1")
        assert store.consume("key1", limit=1, window_seconds=10.0) is True

    def test_clear_all(self):
        store = _InMemoryRateLimitStore()
        store.consume("key1", limit=1, window_seconds=10.0)
        store.consume("key2", limit=1, window_seconds=10.0)
        
        assert store.consume("key1", limit=1, window_seconds=10.0) is False
        assert store.consume("key2", limit=1, window_seconds=10.0) is False
        
        store.clear_all()
        assert store.consume("key1", limit=1, window_seconds=10.0) is True
        assert store.consume("key2", limit=1, window_seconds=10.0) is True


class TestDbRateLimitStore:
    @patch("app.core.db_access.execute_db")
    @patch("app.core.db_access.query_db")
    def test_consume_under_limit(self, mock_query, mock_execute):
        mock_query.return_value = {"cnt": 2}
        store = _DbRateLimitStore()
        
        # limit is 5, count is 2 -> should consume
        assert store.consume("db_key", limit=5, window_seconds=60.0) is True
        assert mock_execute.call_count == 2  # DELETE + INSERT

    @patch("app.core.db_access.execute_db")
    @patch("app.core.db_access.query_db")
    def test_consume_at_limit(self, mock_query, mock_execute):
        mock_query.return_value = {"cnt": 5}
        store = _DbRateLimitStore()
        
        # limit is 5, count is 5 -> should block
        assert store.consume("db_key", limit=5, window_seconds=60.0) is False
        assert mock_execute.call_count == 1  # DELETE only

    @patch("app.core.db_access.execute_db")
    def test_record_failure(self, mock_execute):
        store = _DbRateLimitStore()
        store.record_failure("db_key")
        assert mock_execute.call_count == 2  # INSERT + DELETE old

    @patch("app.core.db_access.execute_db")
    @patch("app.core.db_access.query_db")
    def test_is_locked_out(self, mock_query, mock_execute):
        store = _DbRateLimitStore()
        now = time.time()
        # Simulate 6 hits
        mock_query.return_value = [
            {"hit_epoch": now - 10},
            {"hit_epoch": now - 8},
            {"hit_epoch": now - 6},
            {"hit_epoch": now - 4},
            {"hit_epoch": now - 2},
            {"hit_epoch": now - 1},
        ]
        assert store.is_locked_out("db_key", max_attempts=5, window_s=300, lockout_s=60) is True

    @patch("app.core.db_access.execute_db")
    def test_clear(self, mock_execute):
        store = _DbRateLimitStore()
        store.clear("db_key")
        mock_execute.assert_called_once()
        assert "DELETE" in mock_execute.call_args[0][0]
