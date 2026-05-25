from __future__ import annotations
import time
from app.core.db_access import execute_db, query_db

class RateLimitStore:
    @staticmethod
    def consume(key: str, limit: int, window_seconds: float) -> bool:
        # Clean up key-specific events older than the window
        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - %s * INTERVAL '1 second'",
            (key, window_seconds)
        )
        # Count remaining hits in the window
        row = query_db(
            "SELECT COUNT(*) AS cnt FROM rate_limit_events WHERE key = %s",
            (key,),
            one=True
        )
        count = int(row["cnt"] if row else 0)
        if count >= limit:
            return False
        # Record hit
        execute_db(
            "INSERT INTO rate_limit_events (key, hit_at) VALUES (%s, NOW())",
            (key,)
        )
        return True

    @staticmethod
    def record_failure(key: str) -> None:
        # Record hit
        execute_db(
            "INSERT INTO rate_limit_events (key, hit_at) VALUES (%s, NOW())",
            (key,)
        )
        # Cleanup hits older than 24 hours to keep the table size small
        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - INTERVAL '24 hours'",
            (key,)
        )

    @staticmethod
    def is_locked_out(key: str, max_attempts: int, window_s: float, lockout_s: float) -> bool:
        # Prune hits that cannot possibly affect the lockout status anymore
        max_age = max(window_s, lockout_s * 16.0)
        execute_db(
            "DELETE FROM rate_limit_events WHERE key = %s AND hit_at < NOW() - %s * INTERVAL '1 second'",
            (key, max_age)
        )
        # Retrieve recent hits
        rows = query_db(
            "SELECT EXTRACT(EPOCH FROM hit_at) AS hit_epoch FROM rate_limit_events WHERE key = %s ORDER BY hit_at ASC",
            (key,)
        )
        hits = [float(r["hit_epoch"]) for r in rows] if rows else []
        now = time.time()
        # Filter hits in the lockout window
        recent_hits = [h for h in hits if now - h < window_s]
        if len(recent_hits) >= max_attempts:
            extra_attempts = len(recent_hits) - max_attempts
            lockout_time = lockout_s * (2 ** min(extra_attempts, 4))
            last_failure = max(recent_hits) if recent_hits else 0
            return (now - last_failure) < lockout_time
        return False

    @staticmethod
    def clear(key: str) -> None:
        execute_db("DELETE FROM rate_limit_events WHERE key = %s", (key,))
