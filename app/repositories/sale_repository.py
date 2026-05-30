from __future__ import annotations

from app.core.db_access import db_task, query_db, query_db_async
from app.core.perf_cache import cached_result, invalidate_cache_domain

def _is_other_operation_item(name: str | None) -> bool:
    return str(name or "").strip().casefold() == "autre"

def invalidate_sellable_items_cache() -> None:
    invalidate_cache_domain("sales_sellable_items")
    from app.core.perf_cache import invalidate_cache_domains
    invalidate_cache_domains("dashboard", "sales", "client")

def _load_sellable_items():
    items = []
    for product in query_db("SELECT id, name, default_unit AS unit, stock_qty, sale_price, avg_cost FROM finished_products ORDER BY name"):
        items.append({
            "key": f"finished:{product['id']}",
            "label": f"{product['name']} - produit final",
            "unit": product["unit"],
            "stock_qty": product["stock_qty"],
            "sale_price": product["sale_price"],
            "avg_cost": product["avg_cost"],
            "force_unit": "",
            "custom_name_required": "",
        })
    for raw_material in query_db("""
        SELECT id, name, unit, stock_qty, sale_price, avg_cost
        FROM raw_materials
        ORDER BY CASE WHEN upper(trim(name)) = 'AUTRE' THEN 1 ELSE 0 END, name
    """):
        is_other = _is_other_operation_item(raw_material["name"])
        items.append({
            "key": f"raw:{raw_material['id']}",
            "label": f"{raw_material['name']} - {'autre produit' if is_other else 'matière première'}",
            "unit": raw_material["unit"],
            "stock_qty": raw_material["stock_qty"],
            "sale_price": raw_material["sale_price"],
            "avg_cost": raw_material["avg_cost"],
            "force_unit": "unite" if is_other else "",
            "custom_name_required": "1" if is_other else "",
        })
    return items

@db_task
def build_sellable_items():
    from app.core.perf_cache import TTL_SEMI_STABLE
    return cached_result(("sales_sellable_items",), _load_sellable_items, ttl_seconds=TTL_SEMI_STABLE)

async def list_sales(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    where: list[str] = []
    params: list[object] = []
    
    if search:
        like = f"%{search}%"
        where.append("(LOWER(COALESCE(client_name, '')) LIKE LOWER(%s) OR LOWER(COALESCE(item_name, '')) LIKE LOWER(%s) OR LOWER(COALESCE(notes, '')) LIKE LOWER(%s))")
        params.extend([like, like, like])
        
    if date_from:
        where.append("sale_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("sale_date <= %s")
        params.append(date_to)
        
    if kind in {"finished", "raw"}:
        where.append("row_kind = %s")
        params.append(kind)
        
    if status == "paid":
        where.append("balance_due <= 0")
    elif status == "due":
        where.append("balance_due > 0")
    elif status in {"cash", "credit"}:
        where.append("sale_type = %s")
        params.append(status)
        
    base_query = """
        SELECT * FROM (
            SELECT s.id, s.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                   s.document_id, s.quantity, s.unit, s.total, s.amount_paid, s.balance_due, s.profit_amount, s.sale_type, s.notes,
                   'Produit fini' AS item_kind, 'finished' AS row_kind
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            UNION ALL
            SELECT rs.id, rs.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, r.name AS item_name,
                   rs.document_id, rs.quantity, rs.unit, rs.total, rs.amount_paid, rs.balance_due, rs.profit_amount, rs.sale_type, rs.notes,
                   'Matiere premiere' AS item_kind, 'raw' AS row_kind
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
        ) x
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY sale_date DESC, id DESC LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total


@db_task
def get_sale(kind: str, row_id: int):
    if kind == "finished":
        return query_db("""
            SELECT s.*, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                   '' AS custom_item_name, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.id = %s
        """, (row_id,), one=True)
    return query_db("""
        SELECT rs.*, COALESCE(c.name, 'Comptoir') AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
               rs.custom_item_name, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key
        FROM raw_sales rs
        LEFT JOIN clients c ON c.id = rs.client_id
        JOIN raw_materials r ON r.id = rs.raw_material_id
        WHERE rs.id = %s
    """, (row_id,), one=True)
@db_task
def get_sale_document(document_id: int):
    return query_db("SELECT * FROM sale_documents WHERE id = %s", (document_id,), one=True)


@db_task
def list_sale_document_lines(document_id: int):
    return query_db(
        """
        SELECT * FROM (
            SELECT s.id AS row_id, s.document_id, s.sale_date, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due,
                   f.name AS item_name, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key,
                   'Produit fini' AS item_kind, '' AS custom_item_name
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.document_id = %s
            UNION ALL
            SELECT rs.id AS row_id, rs.document_id, rs.sale_date, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due,
                   r.name AS item_name, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key,
                   'Matiere premiere' AS item_kind, rs.custom_item_name
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.document_id = %s
        ) x ORDER BY row_id
        """,
        (document_id, document_id),
    )
