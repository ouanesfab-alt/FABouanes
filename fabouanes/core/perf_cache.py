from __future__ import annotations

import hashlib
import os
import pickle
from collections import OrderedDict
from time import monotonic
from typing import Any, Callable, Hashable

from fabouanes.config import DATABASE_URL

try:
    import redis
except Exception:  # pragma: no cover - redis optional
    redis = None


_CACHE: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
_MAX_ENTRIES = 96
_REDIS_CLIENT = None
_REDIS_DISABLED = False
_CACHE_EPOCH = 0
_REDIS_EPOCH_KEY = "fabouanes:cache:epoch:v1"


def _database_fingerprint() -> str:
    epoch = _CACHE_EPOCH
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            raw_epoch = redis_client.get(_REDIS_EPOCH_KEY)
            if raw_epoch is not None:
                epoch = int(raw_epoch)
        except Exception:
            pass
    return f"postgres:{hash(DATABASE_URL)}:{epoch}"


def _redis_url() -> str:
    return str(os.environ.get("REDIS_URL", "") or "").strip()


def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_DISABLED
    if _REDIS_DISABLED:
        return None
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if redis is None:
        _REDIS_DISABLED = True
        return None
    url = _redis_url()
    if not url:
        _REDIS_DISABLED = True
        return None
    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=False,
            socket_connect_timeout=0.4,
            socket_timeout=0.4,
            health_check_interval=30,
        )
        client.ping()
    except Exception:
        _REDIS_DISABLED = True
        return None
    _REDIS_CLIENT = client
    return _REDIS_CLIENT


def _redis_cache_key(key_parts: tuple[Hashable, ...], fingerprint: str) -> str:
    raw = repr((key_parts, fingerprint)).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(raw).hexdigest()
    return f"fabouanes:cache:v1:{digest}"


def _local_cache_get(cache_key: tuple[Hashable, ...], *, now: float, fingerprint: str):
    entry = _CACHE.get(cache_key)
    if entry and entry["expires_at"] > now and entry["fingerprint"] == fingerprint:
        _CACHE.move_to_end(cache_key)
        return entry["value"]
    return None


def _local_cache_set(cache_key: tuple[Hashable, ...], *, now: float, ttl_seconds: float, fingerprint: str, value: Any) -> None:
    _CACHE[cache_key] = {
        "expires_at": now + max(0.5, float(ttl_seconds or 0)),
        "fingerprint": fingerprint,
        "value": value,
    }
    _CACHE.move_to_end(cache_key)
    while len(_CACHE) > _MAX_ENTRIES:
        _CACHE.popitem(last=False)


def cached_result(
    key_parts: tuple[Hashable, ...],
    builder: Callable[[], Any],
    *,
    ttl_seconds: float = 5.0,
) -> Any:
    now = monotonic()
    cache_key = tuple(key_parts)
    fingerprint = _database_fingerprint()

    local_value = _local_cache_get(cache_key, now=now, fingerprint=fingerprint)
    if local_value is not None:
        return local_value

    ttl = max(1, int(round(max(0.5, float(ttl_seconds or 0)))))
    redis_client = _get_redis_client()
    redis_key = _redis_cache_key(cache_key, fingerprint)
    if redis_client is not None:
        try:
            payload = redis_client.get(redis_key)
            if payload is not None:
                value = pickle.loads(payload)
                _local_cache_set(cache_key, now=now, ttl_seconds=ttl_seconds, fingerprint=fingerprint, value=value)
                return value
        except Exception:
            pass

    value = builder()
    _local_cache_set(cache_key, now=now, ttl_seconds=ttl_seconds, fingerprint=fingerprint, value=value)
    if redis_client is not None:
        try:
            redis_client.setex(redis_key, ttl, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            pass
    return value


def cache_entry_count() -> int:
    return len(_CACHE)


def mark_cache_dirty() -> None:
    global _CACHE_EPOCH
    _CACHE_EPOCH += 1
    _CACHE.clear()
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            redis_client.incr(_REDIS_EPOCH_KEY)
        except Exception:
            pass
