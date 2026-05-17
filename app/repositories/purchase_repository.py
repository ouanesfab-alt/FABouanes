from __future__ import annotations

from app.core.db_access import query_db
from app.utils.pagination import decode_cursor, encode_cursor, keyset_pagination_context, paginated_rows, pagination_context, parse_pagination


def _raw_material_choices():
    return query_db(
        """
        SELECT *,
               CASE
                   WHEN upper(trim(name)) = 'AUTRE' THEN name || ' - autre produit'
                   ELSE name
               END AS option_label,
               CASE
                   WHEN upper(trim(name)) = 'AUTRE' THEN 'unite'
                   ELSE ''
               END AS force_unit,
               CASE
                   WHEN upper(trim(name)) = 'AUTRE' THEN '1'
                   ELSE ''
               END AS custom_name_required
        FROM raw_materials
        ORDER BY CASE WHEN upper(trim(name)) = 'AUTRE' THEN 1 ELSE 0 END, name
        """
    )


def list_purchase_page_context(args=None):
    page, page_size, offset = parse_pagination(args or {})
    cursor = decode_cursor(str((args or {}).get("cursor", "") or ""), 2)
    where: list[str] = []
    params: list[object] = []
    q = str((args or {}).get("q", "") or "").strip()
    purchase_date = str((args or {}).get("date", "") or "").strip()
    if q:
        where.append("LOWER(COALESCE(supplier_name, '') || ' ' || COALESCE(material_name, '')) LIKE LOWER(?)")
        params.append(f"%{q}%")
    if purchase_date:
        where.append("purchase_date = ?")
        params.append(purchase_date)
    query = """
        SELECT * FROM (
            SELECT p.*, s.name AS supplier_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS material_name, COALESCE(p.unit, r.unit, 'kg') AS material_unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS display_quantity,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS display_unit_price
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            JOIN raw_materials r ON r.id = p.raw_material_id
        ) x
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    total_row = query_db(f"SELECT COUNT(*) AS c FROM ({query}) purchases_count", tuple(params), one=True)
    total = int(total_row["c"] if total_row else 0)
    cursor_where = ""
    cursor_params: list[object] = []
    if cursor:
        try:
            cursor_id = int(cursor[1])
        except (TypeError, ValueError):
            cursor_id = 0
        if cursor_id > 0:
            cursor_where = " AND " if where else " WHERE "
            cursor_where += "(purchase_date < ? OR (purchase_date = ? AND id < ?))"
            cursor_params.extend([cursor[0], cursor[0], cursor_id])
    rows_plus = query_db(
        f"{query}{cursor_where} ORDER BY purchase_date DESC, id DESC LIMIT ?",
        tuple(params + cursor_params + [page_size + 1]),
    )
    has_next = len(rows_plus) > page_size
    rows = rows_plus[:page_size]
    next_cursor = ""
    if has_next and rows:
        last = rows[-1]
        next_cursor = encode_cursor(last["purchase_date"], last["id"])
    return {
        "purchases": rows,
        "suppliers": query_db("SELECT * FROM suppliers ORDER BY name"),
        "raw_materials": _raw_material_choices(),
        "filters": {"q": q, "date": purchase_date},
        "pagination": keyset_pagination_context(
            "purchases",
            args or {},
            total=total,
            page=page,
            page_size=page_size,
            returned=len(rows),
            next_cursor=next_cursor,
        ),
    }


def list_purchase_form_context():
    return {
        "suppliers": query_db("SELECT * FROM suppliers ORDER BY name"),
        "raw_materials": _raw_material_choices(),
    }


def get_purchase(purchase_id: int):
    return query_db(
        """
        SELECT p.*, s.name AS supplier_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS material_name,
               COALESCE(p.unit, r.unit, 'kg') AS display_unit,
               CASE
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                   ELSE p.quantity
               END AS display_quantity,
               CASE
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                   ELSE p.unit_price
               END AS display_unit_price
        FROM purchases p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.id = ?
        """,
        (purchase_id,),
        one=True,
    )


def get_purchase_document(document_id: int):
    return query_db(
        """
        SELECT pd.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name
        FROM purchase_documents pd
        LEFT JOIN suppliers s ON s.id = pd.supplier_id
        WHERE pd.id = ?
        """,
        (document_id,),
        one=True,
    )


def list_purchase_document_lines(document_id: int):
    return query_db(
        """
        SELECT p.id AS row_id, p.document_id, p.supplier_id, p.purchase_date, p.notes, p.raw_material_id,
               COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS material_name, p.custom_item_name,
               COALESCE(p.unit, r.unit, 'kg') AS display_unit,
               CASE
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                   ELSE p.quantity
               END AS display_quantity,
               CASE
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                   WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                   ELSE p.unit_price
               END AS display_unit_price,
               p.total
        FROM purchases p
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.document_id = ?
        ORDER BY p.id ASC
        """,
        (document_id,),
    )
async def list_purchases(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(COALESCE(s.name, '')) LIKE LOWER(?) OR LOWER(COALESCE(r.name, '')) LIKE LOWER(?) OR LOWER(COALESCE(p.notes, '')) LIKE LOWER(?))")
        like = f"%{search}%"
        params.extend([like, like, like])
        
    if date_from:
        where.append("p.purchase_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("p.purchase_date <= ?")
        params.append(date_to)
        
    base_query = """
        SELECT p.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name, r.name AS material_name, r.unit AS material_unit
        FROM purchases p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        JOIN raw_materials r ON r.id = p.raw_material_id
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    from app.core.config import settings
    offset = (page - 1) * page_size
    
    if settings.uses_postgres:
        wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY p.purchase_date DESC, p.id DESC LIMIT ? OFFSET ?"
        rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
        total = int(rows[0]["_total_count"]) if rows else 0
        return [dict(r) for r in rows], total
        
    count_row = await query_db_async(f"SELECT COUNT(*) AS c FROM ({base_query}) _q", tuple(params), one=True)
    total = int(count_row["c"] if count_row else 0)
    
    rows = await query_db_async(f"{base_query} ORDER BY p.purchase_date DESC, p.id DESC LIMIT ? OFFSET ?", tuple(params) + (page_size, offset))
    return [dict(r) for r in rows], total

