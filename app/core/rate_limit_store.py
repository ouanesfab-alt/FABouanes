"""In-memory rate limit store with thread-safe operations.

Replaces the previous DB-backed rate limiter to eliminate 3 SQL queries
per rate-limited HTTP request (DELETE + SELECT + INSERT).

Falls back to DB-backed implementation for multi-worker deployments
via ``FAB_RATE_LIMIT_BACKEND=db`` environment variable.
"""
from __future__ import annotations

import os
import time
import threading
from collections import defaultdict


# Allow falling back to DB-backed rate limiting for multi-worker setups
_BACKEND_MODE = os.environ.get("FAB_RATE_LIMIT_BACKEND", "memory").strip().lower()


class _InMemoryRateLimitStore:
    """Thread-safe in-memory rate limiter with automatic TTL cleanup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}  # key -> lockout_until (monotonic)

    # ── Core API ────────────────────────────────────────────────

    def consume(self, key: str, limit: int, window_seconds: float) -> bool:
        """Record a hit and return True if under the limit."""
        now = time.monotonic()
        with self._lock:
            self._purge(key, now, window_seconds)
            if len(self._attempts[key]) >= limit:
                return False
            self._attempts[key].append(now)
            return True

    def record_failure(self, key: str) -> None:
        """Record a login failure (no window pruning — just append)."""
        now = time.monotonic()
        with self._lock:
            self._attempts[key].append(now)
            # Keep at most 100 entries per key to bound memory
            if len(self._attempts[key]) > 100:
                self._attempts[key] = self._attempts[key][-100:]

    def is_locked_out(
        self, key: str, max_attempts: int, window_s: float, lockout_s: float
    ) -> bool:
        """Check if *key* is locked out with exponential backoff."""
        now = time.monotonic()
        with self._lock:
            # Check explicit lockout first
            until = self._lockouts.get(key, 0)
            if now < until:
                return True

            # Count recent failures inside the window
            recent = [t for t in self._attempts.get(key, []) if now - t < window_s]
            if len(recent) < max_attempts:
                return False

            # Exponential backoff: lockout_s * 2^extra (capped at 2^4 = 16x)
            extra = len(recent) - max_attempts
            lockout_time = lockout_s * (2 ** min(extra, 4))
            last_failure = max(recent) if recent else 0
            if (now - last_failure) < lockout_time:
                return True

            return False

    def clear(self, key: str) -> None:
        """Clear all rate-limit data for *key*."""
        with self._lock:
            self._attempts.pop(key, None)
            self._lockouts.pop(key, None)

    def clear_all(self) -> None:
        """Clear everything (mainly for tests)."""
        with self._lock:
            self._attempts.clear()
            self._lockouts.clear()

    # ── Internal ────────────────────────────────────────────────

    def _purge(self, key: str, now: float, window: float) -> None:
        """Remove entries older than *window* seconds (caller holds lock)."""
        self._attempts[key] = [
            t for t in self._attempts[key] if now - t < window
        ]


class _DbRateLimitStore:
    """DB-backed rate limiter for multi-worker deployments (original behaviour)."""

    @staticmethod
    def consume(key: str, limit: int, window_seconds: float) -> bool:
        from app.core.db_access import execute_db, query_db

        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - %s * INTERVAL '1 second'",
            (key, window_seconds),
        )
        row = query_db(
            "SELECT COUNT(*) AS cnt FROM rate_limit_events WHERE key = %s",
            (key,),
            one=True,
        )
        count = int(row["cnt"] if row else 0)
        if count >= limit:
            return False
        execute_db(
            "INSERT INTO rate_limit_events (key, hit_at) VALUES (%s, NOW())",
            (key,),
        )
        return True

    @staticmethod
    def record_failure(key: str) -> None:
        from app.core.db_access import execute_db

        execute_db(
            "INSERT INTO rate_limit_events (key, hit_at) VALUES (%s, NOW())",
            (key,),
        )
        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - INTERVAL '24 hours'",
            (key,),
        )

    @staticmethod
    def is_locked_out(
        key: str, max_attempts: int, window_s: float, lockout_s: float
    ) -> bool:
        import time as _time
        from app.core.db_access import execute_db, query_db

        max_age = max(window_s, lockout_s * 16.0)
        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - %s * INTERVAL '1 second'",
            (key, max_age),
        )
        rows = query_db(
            "SELECT EXTRACT(EPOCH FROM hit_at) AS hit_epoch FROM rate_limit_events WHERE key = %s ORDER BY hit_at ASC",
            (key,),
        )
        hits = [float(r["hit_epoch"]) for r in rows] if rows else []
        now = _time.time()
        recent_hits = [h for h in hits if now - h < window_s]
        if len(recent_hits) >= max_attempts:
            extra_attempts = len(recent_hits) - max_attempts
            lockout_time = lockout_s * (2 ** min(extra_attempts, 4))
            last_failure = max(recent_hits) if recent_hits else 0
            return (now - last_failure) < lockout_time
        return False

    @staticmethod
    def clear(key: str) -> None:
        from app.core.db_access import execute_db
        execute_db("DELETE FROM rate_limit_events WHERE key = %s", (key,))

    def clear_all(self) -> None:
        from app.core.db_access import execute_db
        try:
            execute_db("DELETE FROM rate_limit_events")
        except Exception:
            pass


class _RedisRateLimitStore:
    """Redis-backed sliding window rate limiter with fallback support."""
    def __init__(self, redis_client) -> None:
        self.redis_client = redis_client

    def consume(self, key: str, limit: int, window_seconds: float) -> bool:
        try:
            import time
            import uuid
            now = time.time()
            redis_key = f"fabouanes:ratelimit:{key}"
            # Unique member so multiple hits in the same millisecond are distinct
            member = f"{now}:{uuid.uuid4().hex}"
            
            pipe = self.redis_client.pipeline()
            # 1. Remove hits older than the window
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            # 2. Get card of hits
            pipe.zcard(redis_key)
            # 3. Add current hit
            pipe.zadd(redis_key, {member: now})
            # 4. Set TTL on the key to clean up zset if inactive
            pipe.expire(redis_key, int(window_seconds) + 10)
            
            res = pipe.execute()
            count = res[1]  # zcard result
            
            if count >= limit:
                # We exceeded limit, remove the one we just added
                self.redis_client.zrem(redis_key, member)
                return False
            return True
        except Exception as exc:
            import logging
            logging.getLogger("fabouanes.ratelimit").warning("Redis rate limit consume failed, falling back: %s", exc)
            return _fallback_store.consume(key, limit, window_seconds)

    def record_failure(self, key: str) -> None:
        try:
            import time
            import uuid
            now = time.time()
            redis_key = f"fabouanes:lockout:failures:{key}"
            member = f"{now}:{uuid.uuid4().hex}"
            pipe = self.redis_client.pipeline()
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, 86400)  # Keep for 24h
            pipe.execute()
        except Exception as exc:
            import logging
            logging.getLogger("fabouanes.ratelimit").warning("Redis record_failure failed: %s", exc)
            _fallback_store.record_failure(key)

    def is_locked_out(self, key: str, max_attempts: int, window_s: float, lockout_s: float) -> bool:
        try:
            import time
            now = time.time()
            # Explicit lockout check
            lockout_key = f"fabouanes:lockout:active:{key}"
            until = self.redis_client.get(lockout_key)
            if until and now < float(until.decode("utf-8") if isinstance(until, bytes) else until):
                return True
            
            # Count recent failures
            failures_key = f"fabouanes:lockout:failures:{key}"
            # Prune old failures
            self.redis_client.zremrangebyscore(failures_key, 0, now - window_s)
            
            recent_count = self.redis_client.zcard(failures_key)
            if recent_count < max_attempts:
                return False
            
            # Fetch failure timestamps
            failures = self.redis_client.zrangebyscore(failures_key, now - window_s, now, withscores=True)
            hits = [float(score) for member, score in failures]
            
            extra_attempts = len(hits) - max_attempts
            lockout_time = lockout_s * (2 ** min(extra_attempts, 4))
            last_failure = max(hits) if hits else 0
            
            if (now - last_failure) < lockout_time:
                # Set explicit lockout in Redis
                self.redis_client.setex(lockout_key, int(lockout_time), str(last_failure + lockout_time))
                return True
            return False
        except Exception as exc:
            import logging
            logging.getLogger("fabouanes.ratelimit").warning("Redis is_locked_out check failed, falling back: %s", exc)
            return _fallback_store.is_locked_out(key, max_attempts, window_s, lockout_s)

    def clear(self, key: str) -> None:
        try:
            redis_key = f"fabouanes:ratelimit:{key}"
            failures_key = f"fabouanes:lockout:failures:{key}"
            lockout_key = f"fabouanes:lockout:active:{key}"
            self.redis_client.delete(redis_key, failures_key, lockout_key)
        except Exception:
            pass
        _fallback_store.clear(key)

    def clear_all(self) -> None:
        try:
            keys = self.redis_client.keys("fabouanes:ratelimit:*") + \
                   self.redis_client.keys("fabouanes:lockout:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass
        _fallback_store.clear_all()


# ── Fallback setup ──────────────────────────────────────────────

if _BACKEND_MODE == "db":
    _fallback_store = _DbRateLimitStore()
else:
    _fallback_store = _InMemoryRateLimitStore()


# ── Active Store Selection ───────────────────────────────────────

_redis_client_store = None
_redis_url = os.environ.get("REDIS_URL", "").strip()
if _redis_url:
    try:
        import redis
        _client = redis.from_url(_redis_url)
        _client.ping()
        _redis_client_store = _client
    except Exception:
        pass

if _redis_client_store is not None:
    RateLimitStore = _RedisRateLimitStore(_redis_client_store)
else:
    RateLimitStore = _fallback_store
