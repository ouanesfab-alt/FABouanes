"""
history.py — Helpers for conversation transcript parsing and dangling call pruning.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger("fabouanes.assistant.history")


def get_last_user_query(messages: List[Dict[str, Any]]) -> str:
    """Extrait la dernière requête saisie par l'utilisateur."""
    for m in reversed(messages):
        if m.get("role") == "user":
            parts = m.get("parts", [])
            if isinstance(parts, list):
                return " ".join(p.get("text", "") for p in parts if "text" in p)
            else:
                return str(m.get("content", "") or "")
    return ""


def clean_unconfirmed_tool_calls(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parcourt l'historique et nettoie les appels de fonctions qui n'ont pas reçu
    de réponse (dangling/unconfirmed tool calls).
    """
    cleaned = []
    i = 0
    n = len(messages)
    while i < n:
        msg = messages[i]
        role = msg.get("role")

        has_calls = False
        if role in ("model", "assistant"):
            parts = msg.get("parts")
            if isinstance(parts, list):
                has_calls = any(isinstance(p, dict) and "functionCall" in p for p in parts)
            if msg.get("tool_calls"):
                has_calls = True

        if has_calls:
            has_response = False
            if i + 1 < n:
                next_msg = messages[i + 1]
                if next_msg.get("role") in ("function", "tool"):
                    has_response = True

            if not has_response:
                logger.info(
                    "Assistant: Suppression de l'appel de fonction non confirmé dans l'historique pour éviter les doublons et les erreurs API"
                )
                new_msg = dict(msg)
                if "parts" in new_msg and isinstance(new_msg["parts"], list):
                    new_parts = [p for p in new_msg["parts"] if isinstance(p, dict) and "text" in p]
                    if new_parts:
                        new_msg["parts"] = new_parts
                    else:
                        new_msg = None
                else:
                    new_msg = None

                if new_msg:
                    cleaned.append(new_msg)
                i += 1
                continue

        cleaned.append(msg)
        i += 1

    return cleaned


async def async_list_persisted_threads(limit: int = 15, db=None) -> List[Dict[str, Any]]:
    """Récupère les fils de discussion sauvegardés en base de données de manière asynchrone."""
    try:
        from sqlalchemy import text
        from app.core.uow import unit_of_work

        async with unit_of_work(db) as session:
            stmt = text(
                "SELECT id, title, history, updated_at FROM sabrina_threads ORDER BY updated_at DESC LIMIT :limit"
            )
            res = await session.execute(stmt, {"limit": limit})
            rows = res.mappings().all()
            threads = []
            for r in rows:
                hist = r["history"]
                threads.append(
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "history": hist if isinstance(hist, list) else [],
                        "updated_at": str(r["updated_at"]),
                    }
                )
            return threads
    except Exception as exc:
        logger.warning("Could not list persisted threads: %s", exc)
        return []


def list_persisted_threads(limit: int = 15) -> List[Dict[str, Any]]:
    """Récupère les fils de discussion sauvegardés en base de données."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, async_list_persisted_threads(limit)).result()
    return asyncio.run(async_list_persisted_threads(limit))


async def async_persist_thread(thread_id: str, title: str, history: List[Dict[str, Any]], db=None) -> bool:
    """Sauvegarde ou met à jour un fil de discussion dans PostgreSQL de manière asynchrone."""
    try:
        import json
        from sqlalchemy import text
        from app.core.uow import unit_of_work

        history_json = json.dumps(history, ensure_ascii=False)
        async with unit_of_work(db, auto_commit=True) as session:
            stmt = text(
                """INSERT INTO sabrina_threads (id, title, history, updated_at)
                   VALUES (:id, :title, CAST(:history AS jsonb), CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET
                       title = EXCLUDED.title,
                       history = EXCLUDED.history,
                       updated_at = CURRENT_TIMESTAMP"""
            )
            await session.execute(stmt, {"id": thread_id, "title": title[:250], "history": history_json})
            return True
    except Exception as exc:
        logger.warning("Could not persist thread %s: %s", thread_id, exc)
        return False


def persist_thread(thread_id: str, title: str, history: List[Dict[str, Any]]) -> bool:
    """Sauvegarde ou met à jour un fil de discussion dans PostgreSQL."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(async_persist_thread(thread_id, title, history))
        return True
    return asyncio.run(async_persist_thread(thread_id, title, history))
