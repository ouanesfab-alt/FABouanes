from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any, Callable, Hashable

from app.core.config import APP_DATA_DIR, DATABASE_URL, settings
_CACHE: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
_CACHE_LOCK = RLock()
_INVALIDATION_VERSION = 0

# TTL Constants (seconds)
TTL_STABLE = 3600.0       # 1 hour
TTL_SEMI_STABLE = 300.0   # 5 minutes
TTL_FREQUENT = 30.0       # 30 seconds
TTL_REALTIME = 2.0        # 2 seconds



try:
    _MAX_ENTRIES = max(32, min(10000, int(os.environ.get("FAB_CACHE_MAX_ENTRIES", "512") or "512")))
except Exception:
    _MAX_ENTRIES = 512


def bump_cache_generation() -> int:
    global _INVALIDATION_VERSION
    with _CACHE_LOCK:
        _INVALIDATION_VERSION += 1
        return _INVALIDATION_VERSION


def cache_generation() -> int:
    with _CACHE_LOCK:
        return _INVALIDATION_VERSION


def _database_fingerprint() -> str:
    version = cache_generation()
    return f"v:{version}"


def cached_result(
    key_parts: tuple[Hashable, ...],
    builder: Callable[[], Any],
    *,
    ttl_seconds: float = 5.0,
) -> Any:
    now = monotonic()
    cache_key = tuple(key_parts)
    fingerprint = _database_fingerprint()
    with _CACHE_LOCK:
        entry = _CACHE.get(cache_key)
        if entry and entry["expires_at"] > now and entry["fingerprint"] == fingerprint:
            _CACHE.move_to_end(cache_key)
            return entry["value"]

    value = builder()
    with _CACHE_LOCK:
        _CACHE[cache_key] = {
            "expires_at": now + max(0.5, float(ttl_seconds or 0)),
            "fingerprint": fingerprint,
            "value": value,
        }
        _CACHE.move_to_end(cache_key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return value


def invalidate_cache_domain(domain: str) -> int:
    prefix = str(domain or "").strip()
    if not prefix:
        return 0
    removed = 0
    with _CACHE_LOCK:
        keys_to_remove = [
            k for k in _CACHE
            if k and (str(k[0]) == prefix or str(k[0]).startswith(prefix + ":"))
        ]
        for key in keys_to_remove:
            _CACHE.pop(key, None)
            removed += 1
    return removed


def invalidate_cache_domains(*domains: str) -> int:
    return sum(invalidate_cache_domain(domain) for domain in domains)


def cache_entry_count() -> int:
    with _CACHE_LOCK:
        return len(_CACHE)


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
