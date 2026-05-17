from __future__ import annotations

import re
from functools import lru_cache

from app.core.config import DATABASE_URL


def fts_query(value: str) -> str:
    tokens = re.findall(r"[\w]+", str(value or "").lower(), flags=re.UNICODE)
    return " ".join(f"{token}*" for token in tokens[:8])


@lru_cache(maxsize=16)
def sqlite_fts_enabled(table_name: str) -> bool:
    if DATABASE_URL.lower().startswith("postgres"):
        return False
    try:
        from app.core.db_access import query_db

        row = query_db(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
            one=True,
        )
        return bool(row)
    except Exception:
        return False


def reset_search_capability_cache() -> None:
    sqlite_fts_enabled.cache_clear()
