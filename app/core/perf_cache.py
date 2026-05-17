from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import OrderedDict
from threading import RLock
from time import monotonic
from typing import Any, Callable, Hashable

from app.core.config import settings

# TTL Constants (seconds)
TTL_STABLE = 3600.0       # 1 hour
TTL_SEMI_STABLE = 300.0   # 5 minutes
TTL_FREQUENT = 30.0       # 30 seconds
TTL_REALTIME = 2.0        # 2 seconds

try:
    _MAX_ENTRIES = max(32, min(10000, int(os.environ.get("FAB_CACHE_MAX_ENTRIES", "512") or "512")))
except Exception:
    _MAX_ENTRIES = 512

# --- Cache Backend Abstraction ---

class CacheBackend(ABC):
    @abstractmethod
    def bump_cache_generation(self) -> int:
        pass

    @abstractmethod
    def cache_generation(self) -> int:
        pass

    @abstractmethod
    def get(self, key: tuple[Hashable, ...]) -> Any:
        pass

    @abstractmethod
    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        pass

    @abstractmethod
    def invalidate_domains(self, *domains: str) -> int:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def entry_count(self) -> int:
        pass

# --- InMemoryCache Implementation ---

class InMemoryCache(CacheBackend):
    def __init__(self):
        self._cache: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
        self._lock = RLock()
        self._version = 0

    def bump_cache_generation(self) -> int:
        with self._lock:
            self._version += 1
            return self._version

    def cache_generation(self) -> int:
        with self._lock:
            return self._version

    def get(self, key: tuple[Hashable, ...]) -> Any:
        now = monotonic()
        version = self.cache_generation()
        fingerprint = f"v:{version}"
        with self._lock:
            entry = self._cache.get(key)
            if entry and entry["expires_at"] > now and entry["fingerprint"] == fingerprint:
                self._cache.move_to_end(key)
                return entry["value"]
        return None

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        now = monotonic()
        with self._lock:
            self._cache[key] = {
                "expires_at": now + max(0.5, float(ttl or 0)),
                "fingerprint": fingerprint,
                "value": value,
            }
            self._cache.move_to_end(key)
            while len(self._cache) > _MAX_ENTRIES:
                self._cache.popitem(last=False)

    def invalidate_domains(self, *domains: str) -> int:
        removed = 0
        with self._lock:
            for domain in domains:
                prefix = str(domain or "").strip()
                if not prefix:
                    continue
                keys_to_remove = [
                    k for k in self._cache
                    if k and (str(k[0]) == prefix or str(k[0]).startswith(prefix + ":"))
                ]
                for key in keys_to_remove:
                    self._cache.pop(key, None)
                    removed += 1
            
            # Also increment our generation to be absolutely sure all processes/threads stay in sync
            self.bump_cache_generation()
        return removed

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def entry_count(self) -> int:
        with self._lock:
            return len(self._cache)

# --- RedisCache Implementation (Defensive fallback to InMemoryCache if redis package not available) ---

class RedisCache(CacheBackend):
    def __init__(self, redis_url: str):
        import redis
        self.client = redis.from_url(redis_url)
        self.prefix = "fabouanes:cache:"
        self.gen_key = "fabouanes:cache_generation"

    def _redis_key(self, key: tuple[Hashable, ...]) -> str:
        return self.prefix + ":".join(str(k) for k in key)

    def bump_cache_generation(self) -> int:
        try:
            return self.client.incr(self.gen_key)
        except Exception:
            return 1

    def cache_generation(self) -> int:
        try:
            val = self.client.get(self.gen_key)
            return int(val) if val is not None else 0
        except Exception:
            return 0

    def get(self, key: tuple[Hashable, ...]) -> Any:
        import pickle
        try:
            r_key = self._redis_key(key)
            data = self.client.get(r_key)
            if data:
                entry = pickle.loads(data)
                gen = self.cache_generation()
                if entry.get("fingerprint") == f"v:{gen}":
                    return entry.get("value")
            return None
        except Exception:
            return None

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        import pickle
        try:
            r_key = self._redis_key(key)
            entry = {
                "fingerprint": fingerprint,
                "value": value
            }
            data = pickle.dumps(entry)
            self.client.setex(r_key, max(1, int(ttl)), data)
        except Exception:
            pass

    def invalidate_domains(self, *domains: str) -> int:
        # Atomic O(1) global invalidation via cache generation increment
        self.bump_cache_generation()
        return 1

    def clear(self) -> None:
        try:
            keys = self.client.keys(self.prefix + "*")
            if keys:
                self.client.delete(*keys)
            self.client.delete(self.gen_key)
        except Exception:
            pass

    def entry_count(self) -> int:
        try:
            return len(self.client.keys(self.prefix + "*"))
        except Exception:
            return 0

# --- Cache Backend Selection & Singleton initialization ---

def _initialize_backend() -> CacheBackend:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            import redis
            backend = RedisCache(redis_url)
            # Ping Redis to verify connection
            backend.client.ping()
            return backend
        except Exception:
            # Silent fallback to InMemoryCache if Redis fails to connect
            pass
    return InMemoryCache()

_BACKEND: CacheBackend = _initialize_backend()

# --- Public API Delegates ---

def bump_cache_generation() -> int:
    return _BACKEND.bump_cache_generation()

def cache_generation() -> int:
    return _BACKEND.cache_generation()

def _database_fingerprint() -> str:
    version = cache_generation()
    return f"v:{version}"

def cached_result(
    key_parts: tuple[Hashable, ...],
    builder: Callable[[], Any],
    *,
    ttl_seconds: float = 5.0,
) -> Any:
    cache_key = tuple(key_parts)
    val = _BACKEND.get(cache_key)
    if val is not None:
        return val

    value = builder()
    fingerprint = _database_fingerprint()
    _BACKEND.set(cache_key, value, ttl_seconds, fingerprint)
    return value

def invalidate_cache_domain(domain: str) -> int:
    return _BACKEND.invalidate_domains(domain)

def invalidate_cache_domains(*domains: str) -> int:
    return _BACKEND.invalidate_domains(*domains)

def cache_entry_count() -> int:
    return _BACKEND.entry_count()

def clear_cache() -> None:
    _BACKEND.clear()
