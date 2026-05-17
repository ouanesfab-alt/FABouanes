from __future__ import annotations

from app.core.db_access import query_db_async

async def list_suppliers(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(name) LIKE LOWER(?) OR LOWER(COALESCE(phone, '')) LIKE LOWER(?) OR LOWER(COALESCE(address, '')) LIKE LOWER(?))")
        like = f"%{search}%"
        params.extend([like, like, like])
        
    base_query = "SELECT * FROM suppliers"
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT ? OFFSET ?"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total

