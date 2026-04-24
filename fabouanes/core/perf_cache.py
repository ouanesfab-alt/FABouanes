from __future__ import annotations

from collections import OrderedDict
from time import monotonic, time
from typing import Any, Callable, Hashable

from fabouanes.config import DATABASE_URL
_CACHE: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
_MAX_ENTRIES = 48


def _database_fingerprint() -> str:
    return f"postgres:{hash(DATABASE_URL)}:{int(time() // 3)}"


def cached_result(
    key_parts: tuple[Hashable, ...],
    builder: Callable[[], Any],
    *,
    ttl_seconds: float = 5.0,
) -> Any:
    now = monotonic()
    cache_key = tuple(key_parts)
    fingerprint = _database_fingerprint()
    entry = _CACHE.get(cache_key)
    if entry and entry["expires_at"] > now and entry["fingerprint"] == fingerprint:
        _CACHE.move_to_end(cache_key)
        return entry["value"]

    value = builder()
    _CACHE[cache_key] = {
        "expires_at": now + max(0.5, float(ttl_seconds or 0)),
        "fingerprint": fingerprint,
        "value": value,
    }
    _CACHE.move_to_end(cache_key)
    while len(_CACHE) > _MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return value


def cache_entry_count() -> int:
    return len(_CACHE)
