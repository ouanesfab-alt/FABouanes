"""
history.py — Helpers for conversation transcript parsing and dangling call pruning.
"""
from __future__ import annotations

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
                logger.info("Assistant: Suppression de l'appel de fonction non confirmé dans l'historique pour éviter les doublons et les erreurs API")
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
