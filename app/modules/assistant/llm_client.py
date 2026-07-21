"""
llm_client.py — Managed HTTP Clients for Gemini and Ollama APIs.
"""
from __future__ import annotations

import logging
import httpx

logger = logging.getLogger("fabouanes.assistant.llm_client")

_gemini_client: httpx.AsyncClient | None = None
_ollama_client: httpx.AsyncClient | None = None


def get_gemini_client() -> httpx.AsyncClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = httpx.AsyncClient(timeout=60.0)
    return _gemini_client


def get_ollama_client() -> httpx.AsyncClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = httpx.AsyncClient(timeout=180.0, trust_env=False)
    return _ollama_client


async def close_http_clients() -> None:
    """Ferme proprement les clients HTTP globaux lors du shutdown."""
    global _gemini_client, _ollama_client
    for name, client in [("gemini", _gemini_client), ("ollama", _ollama_client)]:
        if client is not None:
            try:
                await client.aclose()
                logger.info("Client HTTP %s fermé.", name)
            except Exception as e:
                logger.warning("Erreur lors de la fermeture du client HTTP %s: %s", name, e)
    _gemini_client = None
    _ollama_client = None
