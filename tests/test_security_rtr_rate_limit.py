# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from app.core.jwt_auth import (
    create_refresh_token,
    validate_mobile_refresh_token,
)
from app.api.deps import validate_refresh_token
from app.core.rate_limit_store import _RedisRateLimitStore


@patch("app.core.db_helpers.execute_db")
def test_create_refresh_token_stores_in_db(mock_execute):
    token = create_refresh_token(user_id=123)
    assert isinstance(token, str)
    assert mock_execute.call_count == 1
    args, kwargs = mock_execute.call_args
    assert "INSERT INTO api_refresh_tokens" in args[0]
    assert args[1][0] == 123  # user_id
    assert args[1][2] == token[-8:]  # token_hint


@patch("app.core.db_helpers.execute_db")
@patch("app.core.db_helpers.query_db")
def test_validate_mobile_refresh_token_success(mock_query, mock_execute):
    token = create_refresh_token(user_id=123)
    
    # Mock database responses
    # First query for all_row: unrevoked
    mock_query.return_value = {"id": 1, "user_id": 123, "revoked_at": None}
    
    payload = validate_mobile_refresh_token(token)
    assert payload["sub"] == "123"
    
    # Verify execute_db was called to revoke/mark used the old token
    mock_execute.assert_any_call(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = %s",
        (1,)
    )


@patch("app.core.db_helpers.execute_db")
@patch("app.core.db_helpers.query_db")
def test_validate_mobile_refresh_token_replay_attack(mock_query, mock_execute):
    token = create_refresh_token(user_id=123)
    
    # Mock all_row: already revoked! (replay attack)
    mock_query.return_value = {"id": 1, "user_id": 123, "revoked_at": "2026-07-11 21:00:00"}
    
    with pytest.raises(HTTPException) as exc_info:
        validate_mobile_refresh_token(token)
        
    assert exc_info.value.status_code == 401
    assert "rejeu" in exc_info.value.detail
    
    # Verify it revoked all tokens for user_id 123
    mock_execute.assert_any_call(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
        (123,)
    )
    
    # Verify it revoked all tokens for user_id 123
    mock_execute.assert_any_call(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
        (123,)
    )


@pytest.mark.asyncio
@patch("app.api.deps.execute_db_async", new_callable=AsyncMock)
@patch("app.api.deps.query_db_async", new_callable=AsyncMock)
@patch("app.api.deps.get_user_by_id")
async def test_validate_refresh_token_web_success(mock_get_user, mock_query, mock_execute):
    mock_get_user.return_value = {"id": 456, "username": "testuser", "role": "admin", "is_active": 1}
    
    # query_db_async mock outputs:
    # 1. Replay check (all_row) -> active (revoked_at is None)
    # 2. Expiry check (row) -> active row details
    mock_query.side_effect = [
        {"id": 2, "user_id": 456, "revoked_at": None},
        {"id": 2, "user_id": 456, "expires_at": "2026-08-11 00:00:00"}
    ]
    
    user = await validate_refresh_token("dummy_token")
    assert user is not None
    assert user["id"] == 456
    
    # Verify execute_db_async was called to revoke old token
    mock_execute.assert_any_call(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = %s",
        (2,)
    )


@pytest.mark.asyncio
@patch("app.api.deps.execute_db_async", new_callable=AsyncMock)
@patch("app.api.deps.query_db_async", new_callable=AsyncMock)
async def test_validate_refresh_token_web_replay(mock_query, mock_execute):
    # query_db_async mock outputs:
    # 1. Replay check (all_row) -> already revoked!
    mock_query.return_value = {"id": 2, "user_id": 456, "revoked_at": "2026-07-11 21:00:00"}
    
    user = await validate_refresh_token("dummy_token")
    assert user is None
    
    # Verify execute_db_async was called to revoke all user tokens
    mock_execute.assert_any_call(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
        (456,)
    )


def test_redis_rate_limit_store_consume_under_limit():
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline
    # zremrangebyscore, zcard, zadd, expire
    # zcard is at index 1 in pipeline execute results, return 2 (under limit 5)
    mock_pipeline.execute.return_value = [0, 2, 1, True]
    
    store = _RedisRateLimitStore("redis://localhost:6379")
    store.client = mock_redis
    
    assert store.consume("test_key", limit=5, window_seconds=60) is True
    
    # Verify pipeline operations
    mock_pipeline.zremrangebyscore.assert_called_once()
    mock_pipeline.zcard.assert_called_once()
    mock_pipeline.zadd.assert_called_once()
    mock_pipeline.expire.assert_called_once()


def test_redis_rate_limit_store_consume_over_limit():
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline
    # zcard returns 5 (equal to limit 5)
    mock_pipeline.execute.return_value = [0, 5, 1, True]
    
    store = _RedisRateLimitStore("redis://localhost:6379")
    store.client = mock_redis
    
    assert store.consume("test_key", limit=5, window_seconds=60) is False


@patch("app.core.rate_limit_store._fallback_in_memory")
def test_redis_rate_limit_store_fallback_on_exception(mock_fallback):
    mock_redis = MagicMock()
    mock_redis.pipeline.side_effect = Exception("Redis connection lost")
    mock_fallback.consume.return_value = True
    
    store = _RedisRateLimitStore("redis://localhost:6379")
    store.client = mock_redis
    
    assert store.consume("test_key", limit=5, window_seconds=60) is True
    mock_fallback.consume.assert_called_once_with("test_key", 5, 60)
