from __future__ import annotations

import logging
import threading
from time import monotonic
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("fabouanes.cache")

class CacheEntry:
    def __init__(self, value: Any, ttl_seconds: float):
        self.value = value
        self.expires_at = monotonic() + ttl_seconds

    def is_expired(self) -> bool:
        return monotonic() > self.expires_at

class CacheService:
    """Thread-safe, lightweight local memory cache with TTL support."""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Fetch a value from the cache if it exists and is not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                logger.debug("Cache key expired: %s", key)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store a value in the cache with a specified TTL in seconds."""
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)
            logger.debug("Cache key set: %s with TTL %s", key, ttl_seconds)

    def invalidate(self, key: str) -> None:
        """Remove a single key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("Cache key invalidated: %s", key)

    def clear(self) -> None:
        """Remove all items from the cache."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared entirely")

# Global singleton cache instance
cache_service = CacheService()
