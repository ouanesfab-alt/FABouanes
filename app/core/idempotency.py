from __future__ import annotations

import json
import logging
from typing import Any

from app.core.db_helpers import query_db_async, execute_db_async

logger = logging.getLogger("fabouanes.idempotency")

async def check_idempotency(key: str | None) -> dict[str, Any] | None:
    """
    Checks if a request with the given idempotency key has already been processed.
    Returns the cached response dict if found, otherwise None.
    """
    if not key or not str(key).strip():
        return None

    key = str(key).strip()

    # Fall back to PostgreSQL DB
    try:
        row = await query_db_async(
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


async def save_idempotency(key: str | None, response: dict[str, Any]) -> None:
    """
    Saves the processed response for the given idempotency key to prevent double execution.
    """
    if not key or not str(key).strip():
        return

    key = str(key).strip()
    response_json = json.dumps(response, ensure_ascii=False)

    try:
        await execute_db_async(
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


async def cleanup_expired_idempotency_keys(max_age_days: int = 7) -> int:
    """
    Supprime les entrées d'idempotence plus vieilles que `max_age_days` jours.
    Doit être appelée périodiquement (ex. scheduler quotidien) pour éviter
    que la table `idempotent_requests` ne grossisse indéfiniment.

    Retourne le nombre de lignes supprimées.
    """
    try:
        result = await execute_db_async(
            "DELETE FROM idempotent_requests WHERE created_at < NOW() - (%s * INTERVAL '1 day')",
            (max_age_days,),
        )
        deleted = result.rowcount if hasattr(result, "rowcount") else 0
        logger.info(
            "Idempotency cleanup: deleted %d expired entries (older than %d days)",
            deleted,
            max_age_days,
        )
        return deleted
    except Exception as exc:
        logger.error("Failed to cleanup expired idempotency keys: %s", exc)
        return 0
