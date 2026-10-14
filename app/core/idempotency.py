from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.core.uow import unit_of_work

logger = logging.getLogger("fabouanes.idempotency")


async def check_idempotency(key: str | None, db=None) -> dict[str, Any] | None:
    """Checks if a request with the given idempotency key has already been processed."""
    if not key or not str(key).strip():
        return None

    key = str(key).strip()

    try:
        async with unit_of_work(db) as session:
            stmt = text("SELECT response_json FROM idempotent_requests WHERE key = :key")
            res = await session.execute(stmt, {"key": key})
            val = res.scalar_one_or_none()
            if val:
                logger.info("Idempotency key hit in database: %s", key)
                return json.loads(val)
    except Exception as exc:
        logger.error("Error reading idempotency key from database: %s", exc)

    return None


async def save_idempotency(key: str | None, response: dict[str, Any], db=None) -> None:
    """Saves the processed response for the given idempotency key to prevent double execution."""
    if not key or not str(key).strip():
        return

    key = str(key).strip()
    response_json = json.dumps(response, ensure_ascii=False)

    try:
        async with unit_of_work(db, auto_commit=True) as session:
            stmt = text(
                """
                INSERT INTO idempotent_requests (key, response_json, created_at)
                VALUES (:key, :response_json, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET response_json = EXCLUDED.response_json
                """
            )
            await session.execute(stmt, {"key": key, "response_json": response_json})
            logger.info("Saved idempotency key in database: %s", key)
    except Exception as exc:
        logger.error("Failed to save idempotency key in database: %s", exc)


async def cleanup_expired_idempotency_keys(max_age_days: int = 7, db=None) -> int:
    """Supprime les entrées d'idempotence plus vieilles que `max_age_days` jours."""
    try:
        async with unit_of_work(db, auto_commit=True) as session:
            stmt = text("DELETE FROM idempotent_requests WHERE created_at < NOW() - (:max_age * INTERVAL '1 day')")
            res = await session.execute(stmt, {"max_age": int(max_age_days)})
            deleted = res.rowcount if hasattr(res, "rowcount") else 0
            logger.info(
                "Idempotency cleanup: deleted %d expired entries (older than %d days)",
                deleted,
                max_age_days,
            )
            return deleted
    except Exception as exc:
        logger.error("Failed to cleanup expired idempotency keys: %s", exc)
        return 0
