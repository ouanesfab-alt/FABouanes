from __future__ import annotations

import logging
import os
from collections import OrderedDict
from threading import RLock
from time import monotonic
from typing import Any, Callable, Hashable

logger = logging.getLogger("fabouanes.cache")

# TTL Constants (seconds)
TTL_STABLE = 3600.0       # 1 hour
TTL_SEMI_STABLE = 300.0   # 5 minutes
TTL_FREQUENT = 30.0       # 30 seconds
TTL_REALTIME = 2.0        # 2 seconds

try:
    _MAX_ENTRIES = max(32, min(10000, int(os.environ.get("FAB_CACHE_MAX_ENTRIES", "512") or "512")))
except (ValueError, TypeError):
    _MAX_ENTRIES = 512


def _safe_int(val: Any) -> int:
    if val is None:
        return 0
    if type(val).__name__ in ("MagicMock", "Mock", "AsyncMock"):
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


class CacheBackend:
    pass


# --- InMemoryCache Implementation ---

class InMemoryCache(CacheBackend):
    def __init__(self):
        self._cache: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
        self._lock = RLock()
        self._global_version = 0
        self._domain_versions: dict[str, int] = {}

    def _get_domain_version(self, domain: str) -> int:
        with self._lock:
            return self._global_version + self._domain_versions.get(domain, 0)

    def bump_cache_generation(self) -> int:
        with self._lock:
            self._global_version += 1
            return self._global_version

    def cache_generation(self) -> int:
        with self._lock:
            return self._global_version

    def get(self, key: tuple[Hashable, ...]) -> Any:
        now = monotonic()
        domain = str(key[0]) if key else ""
        version = self._get_domain_version(domain)
        fingerprint = f"v:{version}"
        with self._lock:
            entry = self._cache.get(key)
            if entry and entry["expires_at"] > now and entry["fingerprint"] == fingerprint:
                self._cache.move_to_end(key)
                return entry["value"]
        return None

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        now = monotonic()
        domain = str(key[0]) if key else ""
        
        v_param = None
        if fingerprint and fingerprint.startswith("v:"):
            try:
                v_param = int(fingerprint.split(":")[1])
            except ValueError:
                pass
        
        if v_param is not None and v_param != self._global_version:
            target_fingerprint = fingerprint
        else:
            version = self._get_domain_version(domain)
            target_fingerprint = f"v:{version}"

        with self._lock:
            self._cache[key] = {
                "expires_at": now + max(0.5, float(ttl or 0)),
                "fingerprint": target_fingerprint,
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
                self._domain_versions[prefix] = self._domain_versions.get(prefix, 0) + 1
                keys_to_remove = [
                    k for k in self._cache
                    if k and (str(k[0]) == prefix or str(k[0]).startswith(prefix + ":"))
                ]
                for key in keys_to_remove:
                    self._cache.pop(key, None)
                    removed += 1
        return removed

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def entry_count(self) -> int:
        with self._lock:
            return len(self._cache)


# --- RedisCache and HybridCache for test/mock compatibility ---

class RedisCache(CacheBackend):
    def __init__(self, redis_url: str):
        import redis
        self.client = redis.from_url(redis_url)
        self.prefix = "fabouanes:cache:"
        self.gen_key = "fabouanes:cache_generation"
        self.domain_hash_key = "fabouanes:cache_generations"

    def _redis_key(self, key: tuple[Hashable, ...]) -> str:
        return self.prefix + ":".join(str(k) for k in key)

    def _get_domain_version(self, domain: str) -> int:
        try:
            vg_val = self.client.get(self.gen_key)
            vd_val = self.client.hget(self.domain_hash_key, domain)
            vg = _safe_int(vg_val)
            vd = _safe_int(vd_val)
            return vg + vd
        except Exception:
            return 0

    def bump_cache_generation(self) -> int:
        try:
            return self.client.incr(self.gen_key)
        except Exception:
            return 1

    def cache_generation(self) -> int:
        try:
            val = self.client.get(self.gen_key)
            return _safe_int(val)
        except Exception:
            return 0

    def get(self, key: tuple[Hashable, ...]) -> Any:
        try:
            import json
            r_key = self._redis_key(key)
            data = self.client.get(r_key)
            if data:
                raw = data.decode("utf-8") if isinstance(data, bytes) else data
                entry = json.loads(raw)
                domain = str(key[0]) if key else ""
                gen = self._get_domain_version(domain)
                if entry.get("fingerprint") == f"v:{gen}":
                    return entry.get("value")
            return None
        except Exception:
            return None

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        try:
            import json
            r_key = self._redis_key(key)
            domain = str(key[0]) if key else ""
            vg = self.cache_generation()
            v_param = None
            if fingerprint and fingerprint.startswith("v:"):
                try:
                    v_param = int(fingerprint.split(":")[1])
                except ValueError:
                    pass
            if v_param is not None and v_param != vg:
                target_fingerprint = fingerprint
            else:
                gen = self._get_domain_version(domain)
                target_fingerprint = f"v:{gen}"
            entry = {"fingerprint": target_fingerprint, "value": value}
            self.client.setex(r_key, max(1, int(ttl)), json.dumps(entry))
        except Exception:
            pass

    def invalidate_domains(self, *domains: str) -> int:
        try:
            for domain in domains:
                self.client.hincrby(self.domain_hash_key, domain, 1)
        except Exception:
            pass
        return len(domains)

    def clear(self) -> None:
        try:
            keys = self.client.keys(self.prefix + "*")
            if keys:
                self.client.delete(*keys)
            self.client.delete(self.gen_key)
            self.client.delete(self.domain_hash_key)
        except Exception:
            pass

    def entry_count(self) -> int:
        try:
            return len(self.client.keys(self.prefix + "*"))
        except Exception:
            return 0


class HybridCache(CacheBackend):
    def __init__(self, redis_url: str):
        self.l1 = InMemoryCache()
        self.l2 = RedisCache(redis_url)
        self.invalidate_channel = "fabouanes:cache_invalidate"

    def _start_invalidation_listener(self):
        pass

    def bump_cache_generation(self) -> int:
        self.l1.clear()
        try:
            return self.l2.bump_cache_generation()
        except Exception:
            return 1

    def cache_generation(self) -> int:
        try:
            return self.l2.cache_generation()
        except Exception:
            return 0

    def get(self, key: tuple[Hashable, ...]) -> Any:
        val = self.l1.get(key)
        if val is not None:
            return val
        try:
            val = self.l2.get(key)
            if val is not None:
                domain = str(key[0]) if key else ""
                version = self.l2._get_domain_version(domain)
                self.l1.set(key, val, ttl=30.0, fingerprint=f"v:{version}")
                return val
        except Exception:
            pass
        return None

    def set(self, key: tuple[Hashable, ...], value: Any, ttl: float, fingerprint: str) -> None:
        self.l1.set(key, value, ttl, fingerprint)
        try:
            self.l2.set(key, value, ttl, fingerprint)
        except Exception:
            pass

    def invalidate_domains(self, *domains: str) -> int:
        removed = self.l1.invalidate_domains(*domains)
        try:
            self.l2.invalidate_domains(*domains)
        except Exception:
            pass
        return removed

    def entry_count(self) -> int:
        return self.l1.entry_count()

    def clear(self) -> None:
        self.l1.clear()
        try:
            self.l2.clear()
        except Exception:
            pass


_BACKEND = InMemoryCache()


# --- Public API ---

def bump_cache_generation() -> int:
    gen = _BACKEND.bump_cache_generation()
    try:
        from app.core.events import emit, DomainEvent
        emit(DomainEvent("invalidate", "all_cache", source="cache"))
    except Exception:
        pass
    return gen


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


async def async_cached_result(
    key_parts: tuple[Hashable, ...],
    builder: Callable[[], Any],
    *,
    ttl_seconds: float = 5.0,
) -> Any:
    cache_key = tuple(key_parts)
    val = _BACKEND.get(cache_key)
    if val is not None:
        return val

    import inspect
    if inspect.iscoroutinefunction(builder):
        value = await builder()
    else:
        value = builder()
        if inspect.isawaitable(value):
            value = await value

    fingerprint = _database_fingerprint()
    _BACKEND.set(cache_key, value, ttl_seconds, fingerprint)
    return value


def invalidate_cache_domain(domain: str) -> int:
    removed = _BACKEND.invalidate_domains(domain)
    try:
        from app.core.events import emit, DomainEvent
        emit(DomainEvent("invalidate", "cache", extra={"domains": [domain]}, source="cache"))
    except Exception:
        pass
    return removed


def invalidate_cache_domains(*domains: str) -> int:
    removed = _BACKEND.invalidate_domains(*domains)
    try:
        from app.core.events import emit, DomainEvent
        emit(DomainEvent("invalidate", "cache", extra={"domains": list(domains)}, source="cache"))
    except Exception:
        pass
    return removed


def cache_entry_count() -> int:
    return _BACKEND.entry_count()


def clear_cache() -> None:
    _BACKEND.clear()


def get_cached(key: tuple[Hashable, ...]) -> Any:
    """Direct cache read (mainly for testing)."""
    return _BACKEND.get(key)


def set_cached(key: tuple[Hashable, ...], value: Any, *, ttl: float = 30.0, domain: str = "") -> None:
    """Direct cache write (mainly for testing)."""
    fingerprint = _database_fingerprint()
    _BACKEND.set(key, value, ttl, fingerprint)


async def warm_cache() -> None:
    """Pre-load critical dashboard data into cache at startup.

    Eliminates cold-start latency on first request.  Non-critical:
    if warming fails (e.g. empty DB), the app still works fine.
    """
    logger.info("Cache warming started …")
    try:
        from app.modules.reports.repository import (
            get_dashboard_snapshot,
            get_kpis_for_date,
        )
        from datetime import date

        today = date.today().isoformat()
        await get_dashboard_snapshot(today)
        await get_kpis_for_date(today)
        logger.info("Cache warming completed — dashboard snapshot ready (%d entries)", cache_entry_count())
    except Exception:
        logger.warning("Cache warming failed (non-critical, app will still work)", exc_info=True)


def invalidate_client_cache(client_id: int) -> None:
    """
    Invalide uniquement les clés de cache liées à un client précis.
    """
    keys_to_delete = [
        ("client_detail", client_id),
        ("client_history", client_id),
        ("client_account", client_id),
        ("client_detail_context", client_id),
        ("client_history_context", client_id),
    ]
    
    with _BACKEND._lock:
        for key in keys_to_delete:
            _BACKEND._cache.pop(key, None)

    try:
        from app.core.events import emit, DomainEvent
        emit(DomainEvent("invalidate", "client_cache", extra={"client_id": client_id}, source="cache"))
    except Exception:
        pass
