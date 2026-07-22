"""Lightweight plugin registry for optional module integrations.

This module provides a simple dependency-inversion mechanism so that
``app.core`` never needs to import from ``app.modules.*`` directly.
Optional modules (e.g. the AI assistant) register their callables here at
startup; core code uses the registry to call them without a hard import.

Usage — registration (e.g. in app/modules/assistant/__init__.py):
    from app.core.plugin_registry import registry
    registry.register("get_api_key", get_gemini_api_key)
    registry.register("get_embedding", get_embedding)

Usage — invocation (e.g. in app/core/worker.py):
    from app.core.plugin_registry import registry
    api_key = registry.call("get_api_key")          # returns None if not registered
    embedding = await registry.acall("get_embedding", text, api_key)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger("fabouanes.plugin_registry")


class PluginRegistry:
    """Thread-safe registry for optional callable plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Callable[..., Any]] = {}

    # ── Registration ───────────────────────────────────────────────────────────

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register *fn* under *name*, replacing any previous registration."""
        if name in self._plugins:
            logger.debug("Plugin '%s' overridden by new registration.", name)
        self._plugins[name] = fn
        logger.debug("Plugin '%s' registered: %s", name, fn)

    def unregister(self, name: str) -> None:
        """Remove the registration for *name* (no-op if not registered)."""
        self._plugins.pop(name, None)

    def is_registered(self, name: str) -> bool:
        """Return True if *name* has a registered plugin."""
        return name in self._plugins

    # ── Invocation ─────────────────────────────────────────────────────────────

    def call(self, name: str, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        """Call the plugin registered under *name* synchronously.

        Returns *default* (``None``) if no plugin is registered, without raising.
        """
        fn = self._plugins.get(name)
        if fn is None:
            logger.debug("Plugin '%s' called but not registered — returning default.", name)
            return default
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("Plugin '%s' raised an exception: %s", name, exc)
            return default

    async def acall(self, name: str, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        """Call the plugin registered under *name*, awaiting it if it is a coroutine.

        Returns *default* (``None``) if no plugin is registered, without raising.
        """
        fn = self._plugins.get(name)
        if fn is None:
            logger.debug("Plugin '%s' acalled but not registered — returning default.", name)
            return default
        try:
            result = fn(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as exc:
            logger.warning("Plugin '%s' raised an exception: %s", name, exc)
            return default

    # ── Introspection ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PluginRegistry registered={list(self._plugins)}>"


# Global singleton — import and use this everywhere.
registry: PluginRegistry = PluginRegistry()
