from __future__ import annotations

from app.repositories.client_repository import async_compat
from app.core.db_access import query_db
from app.core.helpers import get_open_credit_entries

@async_compat
async def payment_form_context():
    from app.core.db_access import query_db_async
    return {
        "clients": await query_db_async("SELECT * FROM clients ORDER BY name"),
        "open_sales": await get_open_credit_entries(),
    }


def get_payment(payment_id: int):
    return query_db("SELECT * FROM payments WHERE id = %s", (payment_id,), one=True)
async def list_payments(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(c.name) LIKE LOWER(%s) OR LOWER(COALESCE(p.notes, '')) LIKE LOWER(%s))")
        like = f"%{search}%"
        params.extend([like, like])
        
    if date_from:
        where.append("p.payment_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("p.payment_date <= %s")
        params.append(date_to)
        
    if kind in {"versement", "avance"}:
        where.append("p.payment_type = %s")
        params.append(kind)
        
    base_query = """
        SELECT p.*, c.name AS client_name,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matiere #' || p.raw_sale_id
                   ELSE '-'
               END AS sale_ref
        FROM payments p
        JOIN clients c ON c.id = p.client_id
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY payment_date DESC, id DESC LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total

