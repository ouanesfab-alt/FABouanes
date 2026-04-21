from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from time import monotonic, time
from typing import Any, Callable, Hashable

from fabouanes.config import APP_DATA_DIR, DATABASE_URL

DB_PATH = APP_DATA_DIR / "database.db"
_CACHE: OrderedDict[tuple[Hashable, ...], dict[str, Any]] = OrderedDict()
_MAX_ENTRIES = 48


def _database_fingerprint() -> str:
    if DATABASE_URL.lower().startswith("postgres"):
        return f"postgres:{int(time() // 3)}"
    db_path = Path(DB_PATH)
    if not db_path.exists():
        return "sqlite:missing"
    stat = db_path.stat()
    return f"sqlite:{stat.st_mtime_ns}:{stat.st_size}"


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
