from __future__ import annotations

from math import ceil
from typing import Any

from flask import url_for


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def parse_pagination(args, *, default_page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int, int]:
    try:
        page = int(args.get("page", 1) or 1)
    except Exception:
        page = 1
    try:
        page_size = int(args.get("page_size", default_page_size) or default_page_size)
    except Exception:
        page_size = default_page_size

    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return page, page_size, (page - 1) * page_size


def pagination_context(endpoint: str, args, *, total: int, page: int, page_size: int) -> dict[str, Any]:
    total = max(int(total or 0), 0)
    pages = max(1, ceil(total / page_size)) if page_size else 1
    start = ((page - 1) * page_size) + 1 if total else 0
    end = min(page * page_size, total)

    def make_url(target_page: int) -> str:
        params = dict(args.to_dict(flat=True) if hasattr(args, "to_dict") else dict(args or {}))
        params["page"] = max(int(target_page), 1)
        params["page_size"] = page_size
        return url_for(endpoint, **params)

    return {
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "total": total,
        "start": start,
        "end": end,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_url": make_url(page - 1) if page > 1 else "",
        "next_url": make_url(page + 1) if page < pages else "",
    }


def paginated_rows(query_func, query: str, params: tuple[Any, ...], *, page: int, page_size: int, offset: int):
    count_row = query_func(f"SELECT COUNT(*) AS c FROM ({query}) paginated_query", params, one=True)
    total = int(count_row["c"] if count_row else 0)
    rows = query_func(f"{query} LIMIT ? OFFSET ?", params + (page_size, offset))
    return rows, total
