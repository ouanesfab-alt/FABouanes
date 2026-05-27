from __future__ import annotations

import base64
import json
from math import ceil
from typing import Any
from urllib.parse import urlencode

from app.core.request_state import get_state_value


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def paginate_query(query: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[str, int, int]:
    """Append ``LIMIT``/``OFFSET`` to a SQL query string.

    Returns ``(paginated_query, safe_page_size, offset)`` with clamped bounds.
    """
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size
    return f"{query} LIMIT {page_size} OFFSET {offset}", page_size, offset


def pagination_meta(total: int, page: int, page_size: int) -> dict[str, Any]:
    """Generate pagination metadata dict for API JSON responses."""
    page_size = min(max(1, int(page_size or DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    total = max(0, int(total or 0))
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if page_size else 0,
        "has_next": page * page_size < total,
        "has_prev": page > 1,
    }

def _args_dict(args: Any) -> dict[str, Any]:
    if hasattr(args, "multi_items"):
        result: dict[str, Any] = {}
        for key, value in args.multi_items():
            if key in result:
                existing = result[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    result[key] = [existing, value]
            else:
                result[key] = value
        return result
    if hasattr(args, "to_dict"):
        return dict(args.to_dict(flat=True))
    return dict(args or {})


def _query(params: dict[str, Any]) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return urlencode(clean, doseq=True)


def _url_for(target: str, **params: Any) -> str:
    if target.startswith("/"):
        query = _query(params)
        return f"{target}?{query}" if query else target
    request = get_state_value("request")
    if request is not None:
        from app.web.deps import app_url_for

        return app_url_for(request, target, **params)
    query = _query(params)
    return f"/{target}?{query}" if query else f"/{target}"


def parse_pagination(args: Any, *, default_page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int, int]:
    try:
        page = int((args or {}).get("page", 1) or 1)
    except Exception:
        page = 1
    try:
        page_size = int((args or {}).get("page_size", default_page_size) or default_page_size)
    except Exception:
        page_size = default_page_size
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return page, page_size, (page - 1) * page_size


def pagination_context(
    target: str,
    args: Any,
    *,
    total: int,
    page: int,
    page_size: int,
    route_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = max(int(total or 0), 0)
    pages = max(1, ceil(total / page_size)) if page_size else 1
    start = ((page - 1) * page_size) + 1 if total else 0
    end = min(page * page_size, total)

    def make_url(target_page: int) -> str:
        params = _args_dict(args)
        params.update(route_values or {})
        params["page"] = max(int(target_page), 1)
        params["page_size"] = page_size
        return _url_for(target, **params)

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


def paginate_sequence(rows: list[Any], args: Any, path: str) -> tuple[list[Any], dict[str, Any]]:
    page, page_size, offset = parse_pagination(args)
    total = len(rows)
    return rows[offset : offset + page_size], pagination_context(path, args, total=total, page=page, page_size=page_size)


def paginated_rows(query_func, query: str, params: tuple[Any, ...], *, page: int, page_size: int, offset: int):
    count_row = query_func(f"SELECT COUNT(*) AS c FROM ({query}) paginated_query", params, one=True)
    total = int(count_row["c"] if count_row else 0)
    rows = query_func(f"{query} LIMIT %s OFFSET %s", params + (page_size, offset))
    return rows, total


def encode_cursor(*parts: Any) -> str:
    payload = json.dumps([str(part) for part in parts], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value: str | None, expected_parts: int = 2) -> tuple[str, ...] | None:
    if not value:
        return None
    try:
        padded = value + ("=" * (-len(value) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        parts = tuple(str(part) for part in json.loads(decoded))
    except Exception:
        return None
    if len(parts) != expected_parts:
        return None
    return parts


def keyset_pagination_context(
    target: str,
    args: Any,
    *,
    total: int,
    page: int,
    page_size: int,
    returned: int,
    next_cursor: str,
    route_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = max(int(total or 0), 0)
    start = ((page - 1) * page_size) + 1 if total else 0
    end = min(start + max(returned, 0) - 1, total) if total and returned else 0
    current_cursor = str((args or {}).get("cursor", "") or "") if hasattr(args or {}, "get") else ""

    def make_url(cursor: str = "", target_page: int = 1) -> str:
        params = _args_dict(args)
        params.update(route_values or {})
        params["page"] = max(int(target_page), 1)
        params["page_size"] = page_size
        if cursor:
            params["cursor"] = cursor
        else:
            params.pop("cursor", None)
        return _url_for(target, **params)

    return {
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)) if page_size else 1,
        "total": total,
        "start": start,
        "end": end,
        "has_prev": bool(current_cursor),
        "has_next": bool(next_cursor),
        "prev_url": make_url("", 1) if current_cursor else "",
        "next_url": make_url(next_cursor, page + 1) if next_cursor else "",
        "mode": "keyset",
    }
