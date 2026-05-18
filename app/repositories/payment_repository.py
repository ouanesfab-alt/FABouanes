from __future__ import annotations

from app.core.db_access import query_db
from app.core.helpers import get_open_credit_entries
from app.utils.pagination import paginated_rows, pagination_context, parse_pagination


def list_payment_page_context(args=None):
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    search = str(args.get("q", "") or "").strip()
    payment_date = str(args.get("date", "") or "").strip()
    payment_kind = str(args.get("kind", "") or "").strip().lower()
    where: list[str] = []
    params: list[object] = []
    if search:
        where.append("(LOWER(c.name) LIKE LOWER(%s) OR p.payment_date = %s)")
        params.extend([f"%{search}%", search])
    if payment_date:
        where.append("p.payment_date = %s")
        params.append(payment_date)
    if payment_kind in {"versement", "avance"}:
        where.append("p.payment_type = %s")
        params.append(payment_kind)
    query = """
        SELECT p.id, p.*, c.name AS client_name,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matière #' || p.raw_sale_id
                   ELSE '-'
               END AS sale_ref, p.payment_type
        FROM payments p
        JOIN clients c ON c.id = p.client_id
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY p.id DESC"
    rows, total = paginated_rows(query_db, query, tuple(params), page=page, page_size=page_size, offset=offset)
    return {
        "payments": rows,
        "clients": query_db("SELECT * FROM clients ORDER BY name"),
        "open_sales": get_open_credit_entries(),
        "payment_filters": {"q": search, "date": payment_date, "kind": payment_kind if payment_kind in {"versement", "avance"} else ""},
        "pagination": pagination_context("payments", args, total=total, page=page, page_size=page_size),
    }


def payment_form_context():
    return {
        "clients": query_db("SELECT * FROM clients ORDER BY name"),
        "open_sales": get_open_credit_entries(),
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

