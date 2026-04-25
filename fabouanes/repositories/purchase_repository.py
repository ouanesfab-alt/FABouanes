from __future__ import annotations

from fabouanes.core.db_access import query_db
from fabouanes.core.pagination import paginated_rows, pagination_context, parse_pagination


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
    query += " ORDER BY id DESC"
    rows, total = paginated_rows(query_db, query, tuple(params), page=page, page_size=page_size, offset=offset)
    return {
        "purchases": rows,
        "suppliers": query_db("SELECT * FROM suppliers ORDER BY name"),
        "raw_materials": _raw_material_choices(),
        "filters": {"q": q, "date": purchase_date},
        "pagination": pagination_context("purchases", args or {}, total=total, page=page, page_size=page_size),
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
