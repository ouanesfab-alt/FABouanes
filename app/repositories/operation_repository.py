from __future__ import annotations

from app.core.db_access import query_db_async
from app.repositories.transaction_repository import list_transactions_context


async def list_recent_operations(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("LOWER(COALESCE(partner_name, '') || ' ' || COALESCE(item_name, '') || ' ' || COALESCE(notes, '') || ' ' || COALESCE(operation_label, '')) LIKE LOWER(?)")
        params.append(f"%{search}%")
        
    if date_from:
        where.append("event_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("event_date <= %s")
        params.append(date_to)
        
    if kind in {"sale", "payment", "purchase", "production"}:
        where.append("operation_type = %s")
        params.append(kind)
        
    base_query = """
        SELECT * FROM (
            SELECT 'sale' AS operation_type, s.id AS row_id, s.sale_date AS event_date,
                   COALESCE(c.name, 'Comptoir') AS partner_name, f.name AS item_name, s.notes,
                   s.total AS amount, s.balance_due AS balance_due, 'Vente produit final' AS operation_label
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            UNION ALL
            SELECT 'sale' AS operation_type, rs.id AS row_id, rs.sale_date AS event_date,
                   COALESCE(c.name, 'Comptoir') AS partner_name, r.name AS item_name, rs.notes,
                   rs.total AS amount, rs.balance_due AS balance_due, 'Vente matiere premiere' AS operation_label
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            UNION ALL
            SELECT 'payment' AS operation_type, p.id AS row_id, p.payment_date AS event_date,
                   c.name AS partner_name,
                   CASE WHEN p.payment_type = 'avance' THEN 'Avance client' ELSE 'Versement client' END AS item_name,
                   p.notes, p.amount AS amount, 0 AS balance_due,
                   CASE WHEN p.payment_type = 'avance' THEN 'Avance' ELSE 'Versement' END AS operation_label
            FROM payments p
            JOIN clients c ON c.id = p.client_id
            UNION ALL
            SELECT 'purchase' AS operation_type, p.id AS row_id, p.purchase_date AS event_date,
                   COALESCE(s.name, 'Sans fournisseur') AS partner_name, r.name AS item_name, p.notes,
                   p.total AS amount, 0 AS balance_due, 'Achat' AS operation_label
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            JOIN raw_materials r ON r.id = p.raw_material_id
            UNION ALL
            SELECT 'production' AS operation_type, pb.id AS row_id, pb.production_date AS event_date,
                   '' AS partner_name, fp.name AS item_name, pb.notes,
                   pb.production_cost AS amount, 0 AS balance_due, 'Production' AS operation_label
            FROM production_batches pb
            JOIN finished_products fp ON fp.id = pb.finished_product_id
        ) x
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY event_date DESC, row_id DESC LIMIT %s OFFSET ?"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total



def list_operations_api(args=None) -> tuple[list[dict], dict]:
    context = list_transactions_context(args)
    pagination = dict(context.get("pagination") or {})
    meta = {
        "page": int(pagination.get("page") or 1),
        "limit": int(pagination.get("page_size") or 50),
        "page_size": int(pagination.get("page_size") or 50),
        "total": int(pagination.get("total") or 0),
        "returned": len(context.get("transactions") or []),
        "has_next": bool(pagination.get("has_next")),
        "next_url": pagination.get("next_url") or "",
    }
    return [dict(row) for row in context.get("transactions") or []], meta


__all__ = ["list_recent_operations", "list_operations_api", "list_transactions_context"]
