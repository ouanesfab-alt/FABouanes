"""Tests d'intégration et unitaires ciblés pour hausser la couverture globale > 90%."""
from __future__ import annotations

import sys
import pytest
from unittest import mock

from app.core.rate_limit_store import (
    RateLimitStore,
    _InMemoryRateLimitStore,
    _DbRateLimitStore,
    _RedisRateLimitStore,
)
from app.core.security import validate_password_strength, consume_rate_limit, client_ip
from werkzeug.security import generate_password_hash, check_password_hash
from app.core.jwt_auth import create_access_token, decode_token


def test_in_memory_rate_limit_store_deep():
    store = _InMemoryRateLimitStore()
    key = "test_user_ip_1"

    assert store.consume(key, limit=2, window_seconds=60) is True
    assert store.consume(key, limit=2, window_seconds=60) is True
    assert store.consume(key, limit=2, window_seconds=60) is False

    store.record_failure(key)
    assert store.is_locked_out(key, max_attempts=1, window_s=60.0, lockout_s=300.0) is True

    store.clear(key)
    assert store.consume(key, limit=2, window_seconds=60) is True

    store.clear_user("test_user_ip_1")
    store.clear_all()


def test_rate_limit_store_singleton():
    key = "public_test_key_123"
    assert RateLimitStore.consume(key, limit=5, window_seconds=60) is True
    RateLimitStore.record_failure(key)
    RateLimitStore.clear(key)
    RateLimitStore.clear_user("public_test_key_123")
    RateLimitStore.clear_all()


def test_security_helper_functions():
    valid, _ = validate_password_strength("1234", mode="pin")
    assert valid is False  # 1234 is trivial PIN

    valid_pin, _ = validate_password_strength("7890", mode="pin")
    assert valid_pin is True

    pw = "SecretPassword123!"
    hashed = generate_password_hash(pw)
    assert check_password_hash(hashed, pw) is True
    assert check_password_hash(hashed, "wrong") is False

    token = create_access_token(1, "admin")
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded.get("sub") == "1"


def test_db_rate_limit_store_mocked():
    db_store = _DbRateLimitStore()
    with mock.patch("app.core.db_helpers.execute_db") as mock_exec, \
         mock.patch("app.core.db_helpers.query_db", return_value={"cnt": 0}):
        assert db_store.consume("key1", 5, 60.0) is True
        db_store.record_failure("key1")
        db_store.clear("key1")
        db_store.clear_user("admin")
        db_store.clear_all()


def test_redis_rate_limit_store_fallback():
    mock_redis = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_pipeline = mock.MagicMock()
    mock_pipeline.execute.return_value = [0, 1]
    mock_client.pipeline.return_value = mock_pipeline
    mock_redis.from_url.return_value = mock_client

    with mock.patch.dict("sys.modules", {"redis": mock_redis}):
        store = _RedisRateLimitStore("redis://localhost:6379")
        assert store.consume("test", 5, 60.0) is True
        store.record_failure("test")
        store.clear("test")
        store.clear_user("test")
        store.clear_all()
