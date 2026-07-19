import pytest
import time
import os
from unittest import mock

from app.core.rate_limit_store import (
    _InMemoryRateLimitStore,
    _DbRateLimitStore,
    RateLimitStore,
)

def test_in_memory_rate_limit_store_basic():
    store = _InMemoryRateLimitStore()
    
    # Under limit
    assert store.consume("user1", limit=3, window_seconds=2.0) is True
    assert store.consume("user1", limit=3, window_seconds=2.0) is True
    assert store.consume("user1", limit=3, window_seconds=2.0) is True
    
    # Over limit
    assert store.consume("user1", limit=3, window_seconds=2.0) is False
    
    # Clear specific key
    store.clear("user1")
    assert store.consume("user1", limit=3, window_seconds=2.0) is True

def test_in_memory_lockout_backoff():
    store = _InMemoryRateLimitStore()
    
    # Max attempts = 2, window = 10s, lockout = 1s
    assert store.is_locked_out("user2", max_attempts=2, window_s=10.0, lockout_s=1.0) is False
    
    store.record_failure("user2")
    assert store.is_locked_out("user2", max_attempts=2, window_s=10.0, lockout_s=1.0) is False
    
    store.record_failure("user2")
    # Locked out now!
    assert store.is_locked_out("user2", max_attempts=2, window_s=10.0, lockout_s=1.0) is True
    
    # Check memory bounds
    for _ in range(150):
        store.record_failure("user2")
    assert len(store._attempts["user2"]) <= 100
    
    store.clear_all()
    assert store.is_locked_out("user2", max_attempts=2, window_s=10.0, lockout_s=1.0) is False

def test_db_rate_limit_store():
    # Mock execute_db and query_db to test _DbRateLimitStore without database dependency
    with mock.patch("app.core.db_helpers.execute_db") as mock_execute, \
         mock.patch("app.core.db_helpers.query_db") as mock_query:
        
        mock_query.return_value = {"cnt": 2}
        
        # Consume under limit
        assert _DbRateLimitStore.consume("db_key", limit=5, window_seconds=10.0) is True
        mock_execute.assert_called()
        mock_query.assert_called_once()
        
        # Consume over limit
        mock_query.return_value = {"cnt": 5}
        assert _DbRateLimitStore.consume("db_key", limit=5, window_seconds=10.0) is False
        
        # Lockout check
        mock_query.return_value = [{"hit_epoch": time.time()}]
        assert _DbRateLimitStore.is_locked_out("db_key", max_attempts=2, window_s=10.0, lockout_s=2.0) is False
        
        # Record failure
        _DbRateLimitStore.record_failure("db_key")
        
        # Clear
        _DbRateLimitStore.clear("db_key")
        _DbRateLimitStore().clear_all()

def test_public_rate_limit_apis():
    # Check RateLimitStore functionality
    assert RateLimitStore.consume("pub_key", limit=2, window_seconds=5) is True
    assert RateLimitStore.consume("pub_key", limit=2, window_seconds=5) is True
    assert RateLimitStore.consume("pub_key", limit=2, window_seconds=5) is False
    
    assert RateLimitStore.is_locked_out("pub_key_lock", max_attempts=2, window_s=5, lockout_s=2) is False
    RateLimitStore.record_failure("pub_key_lock")
    RateLimitStore.record_failure("pub_key_lock")
    assert RateLimitStore.is_locked_out("pub_key_lock", max_attempts=2, window_s=5, lockout_s=2) is True
    
    RateLimitStore.clear("pub_key")
    RateLimitStore.clear("pub_key_lock")
