from typing import Any
from fastapi import Request
from app.core.db_access import query_db_async

def pagination_meta(request: Request) -> tuple[int, int, int]:
    page = max(int(request.query_params.get("page", "1") or "1"), 1)
    page_size = min(max(int(request.query_params.get("page_size", "50") or "50"), 1), 100)
    offset = (page - 1) * page_size
    return page, page_size, offset

async def query_list_async(request: Request, query: str, params: tuple[Any, ...] = ()) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page, page_size, offset = pagination_meta(request)
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({query}) _q LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(row) for row in rows], {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total,
    }

def like_value(request: Request) -> str:
    return f"%{request.query_params.get('q', '').strip()}%"

def append_text_search(request: Request, where: list[str], params: list[Any], *fields: str) -> None:
    if not request.query_params.get("q", "").strip():
        return
    clause = " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE LOWER(%s)" for field in fields)
    where.append(f"({clause})")
    like = like_value(request)
    params.extend([like] * len(fields))

def append_date_range(request: Request, where: list[str], params: list[Any], field: str) -> None:
    date_from = str(request.query_params.get("date_from", "") or "").strip()
    date_to = str(request.query_params.get("date_to", "") or "").strip()
    if date_from:
        where.append(f"{field} >= %s")
        params.append(date_from)
    if date_to:
        where.append(f"{field} <= %s")
        params.append(date_to)
