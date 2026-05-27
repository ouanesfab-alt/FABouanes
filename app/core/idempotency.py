from __future__ import annotations

import os
import json
import logging
from typing import Any

from app.core.db_access import query_db, execute_db

logger = logging.getLogger("fabouanes.idempotency")

_redis_client: Any = None
_redis_initialized = False


def _get_redis_client() -> Any:
    global _redis_client, _redis_initialized
    if _redis_initialized:
        return _redis_client

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            import redis
            client = redis.from_url(redis_url)
            client.ping()
            _redis_client = client
            logger.info("Redis initialized successfully for idempotency tracking.")
        except Exception as exc:
            logger.warning("Failed to connect to Redis for idempotency tracking, using DB fallback: %s", exc)
            _redis_client = None
    else:
        _redis_client = None

    _redis_initialized = True
    return _redis_client


def check_idempotency(key: str | None) -> dict[str, Any] | None:
    """
    Checks if a request with the given idempotency key has already been processed.
    Returns the cached response dict if found, otherwise None.
    """
    if not key or not str(key).strip():
        return None

    key = str(key).strip()
    redis_client = _get_redis_client()

    # 1. Try Redis first
    if redis_client is not None:
        try:
            redis_key = f"fabouanes:idempotency:{key}"
            val = redis_client.get(redis_key)
            if val:
                logger.info("Idempotency key hit in Redis: %s", key)
                return json.loads(val)
        except Exception as exc:
            logger.warning("Error reading idempotency key from Redis: %s", exc)

    # 2. Fall back to PostgreSQL DB
    try:
        row = query_db(
            "SELECT response_json FROM idempotent_requests WHERE key = %s",
            (key,),
            one=True,
        )
        if row and row.get("response_json"):
            logger.info("Idempotency key hit in database: %s", key)
            return json.loads(row["response_json"])
    except Exception as exc:
        logger.error("Error reading idempotency key from database: %s", exc)

    return None


def save_idempotency(key: str | None, response: dict[str, Any]) -> None:
    """
    Saves the processed response for the given idempotency key to prevent double execution.
    """
    if not key or not str(key).strip():
        return

    key = str(key).strip()
    response_json = json.dumps(response, ensure_ascii=False)
    redis_client = _get_redis_client()

    saved_in_redis = False

    # 1. Try saving to Redis with 24-hour TTL (86400 seconds)
    if redis_client is not None:
        try:
            redis_key = f"fabouanes:idempotency:{key}"
            redis_client.setex(redis_key, 86400, response_json)
            logger.info("Saved idempotency key in Redis: %s", key)
            saved_in_redis = True
        except Exception as exc:
            logger.warning("Failed to save idempotency key in Redis: %s", exc)

    # 2. If Redis is down or not configured, persist in the database table
    if not saved_in_redis:
        try:
            execute_db(
                """
                INSERT INTO idempotent_requests (key, response_json, created_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET response_json = EXCLUDED.response_json
                """,
                (key, response_json),
            )
            logger.info("Saved idempotency key in database: %s", key)
        except Exception as exc:
            logger.error("Failed to save idempotency key in database: %s", exc)

