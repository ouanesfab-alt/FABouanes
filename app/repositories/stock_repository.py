from __future__ import annotations

from app.core.db_access import execute_db, db_task


@db_task
def insert_stock_movement(
    item_kind: str,
    item_id: int,
    direction: str,
    quantity: float,
    unit: str,
    stock_before: float,
    stock_after: float,
    reason: str,
    reference_type: str,
    reference_id: int | None,
    username: str,
) -> None:
    execute_db(
        """
        INSERT INTO stock_movements (
            item_kind, item_id, direction, quantity, unit, stock_before, stock_after,
            reason, reference_type, reference_id, created_by_username, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            item_kind,
            int(item_id),
            direction,
            float(quantity),
            unit,
            float(stock_before),
            float(stock_after),
            reason,
            reference_type,
            reference_id,
            username,
        ),
    )
async def list_raw_materials(
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(name) LIKE LOWER(%s) OR LOWER(COALESCE(unit, '')) LIKE LOWER(%s))")
        like = f"%{search}%"
        params.extend([like, like])
        
    if status == "low":
        where.append("stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold)")
        
    base_query = """
        SELECT *,
               CASE WHEN stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold) THEN 1 ELSE 0 END AS is_low_stock,
               'raw' AS item_type
        FROM raw_materials
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total



async def list_finished_products(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(name) LIKE LOWER(%s) OR LOWER(COALESCE(default_unit, '')) LIKE LOWER(%s))")
        like = f"%{search}%"
        params.extend([like, like])
        
    base_query = "SELECT *, 'finished' AS item_type FROM finished_products"
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total

