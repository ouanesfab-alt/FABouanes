from __future__ import annotations

from app.utils.pagination import paginate_sequence
from app.core.perf_cache import cached_result
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import execute_db, query_db
from app.core.storage import backup_database


def contacts_context(filter_type: str = "all", filter_name: str = "", args=None, path: str = "/contacts") -> dict:
    normalized_type = (filter_type or "all").strip().lower() or "all"
    normalized_name = (filter_name or "").strip().lower()
    base = cached_result(
        ("contacts_context", normalized_type, normalized_name),
        lambda: _build_contacts_context(normalized_type, normalized_name, filter_name or ""),
        ttl_seconds=6.0,
    )
    contacts, pagination = paginate_sequence(list(base["contacts"]), args or {}, path)
    return {
        **base,
        "contacts": contacts,
        "pagination": pagination,
    }


def _build_contacts_context(filter_type: str, filter_name: str, raw_filter_name: str) -> dict:
    rows = query_db(
        """
        SELECT * FROM (
            SELECT 'Client' AS contact_type, c.id, c.name, c.phone, c.address, c.notes,
                   c.opening_credit
                   + COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id AND s.sale_type = 'credit'), 0)
                   + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id AND rs.sale_type = 'credit'), 0)
                   - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0)
                   + COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'avance'), 0) AS current_balance,
                   COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id), 0)
                   + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id), 0) AS total_amount,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0) AS total_paid,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'avance'), 0) AS total_advance
            FROM clients c
            UNION ALL
            SELECT 'Fournisseur' AS contact_type, s.id, s.name, s.phone, s.address, s.notes,
                   0 AS current_balance,
                   COALESCE((SELECT SUM(total) FROM purchases p WHERE p.supplier_id = s.id), 0) AS total_amount,
                   0 AS total_paid,
                   0 AS total_advance
            FROM suppliers s
        ) x ORDER BY contact_type, name
        """
    )
    filtered_rows = []
    for row in rows:
        if filter_type == "client" and row["contact_type"] != "Client":
            continue
        if filter_type == "supplier" and row["contact_type"] != "Fournisseur":
            continue
        haystack = f"{row['name']} {row['phone'] or ''} {row['address'] or ''}".lower()
        if filter_name and filter_name not in haystack:
            continue
        filtered_rows.append(row)
    return {
        "contacts": filtered_rows,
        "filter_type": filter_type,
        "filter_name": raw_filter_name,
    }


def create_supplier_from_form(form) -> int:
    name = str(form["name"]).strip()
    supplier_id = execute_db(
        "INSERT INTO suppliers (name, phone, address, notes) VALUES (%s, %s, %s, %s)",
        (
            name,
            str(form.get("phone", "")).strip(),
            str(form.get("address", "")).strip(),
            str(form.get("notes", "")).strip(),
        ),
    )
    created = get_supplier(supplier_id)
    log_activity("create_supplier", "supplier", supplier_id, name)
    audit_event("create_supplier", "supplier", supplier_id, after=created)
    backup_database("create_supplier")
    return supplier_id


def get_supplier(supplier_id: int):
    return query_db("SELECT * FROM suppliers WHERE id = %s", (supplier_id,), one=True)


def update_supplier_from_form(supplier_id: int, form) -> None:
    before = get_supplier(supplier_id)
    execute_db(
        "UPDATE suppliers SET name = %s, phone = %s, address = %s, notes = %s WHERE id = %s",
        (
            str(form["name"]).strip(),
            str(form.get("phone", "")).strip(),
            str(form.get("address", "")).strip(),
            str(form.get("notes", "")).strip(),
            supplier_id,
        ),
    )
    updated = get_supplier(supplier_id)
    log_activity("update_supplier", "supplier", supplier_id, str(form["name"]).strip())
    audit_event("update_supplier", "supplier", supplier_id, before=before, after=updated)
    backup_database("update_supplier")


def delete_supplier_by_id(supplier_id: int) -> None:
    before = get_supplier(supplier_id)
    execute_db("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
    log_activity("delete_supplier", "supplier", supplier_id, "Suppression fournisseur")
    audit_event("delete_supplier", "supplier", supplier_id, before=before, after=None)
    backup_database("delete_supplier")


def get_supplier_detail_context(supplier_id: int, args=None, path: str | None = None) -> dict | None:
    base = cached_result(("supplier_detail_context", int(supplier_id)), lambda: _build_supplier_detail_context(supplier_id), ttl_seconds=6.0)
    if not base:
        return None
    purchases, pagination = paginate_sequence(list(base["purchases"]), args or {}, path or f"/contacts/suppliers/{supplier_id}")
    return {
        **base,
        "purchases": purchases,
        "pagination": pagination,
    }


def _build_supplier_detail_context(supplier_id: int) -> dict | None:
    supplier = get_supplier(supplier_id)
    if not supplier:
        return None
    purchases_rows = query_db(
        """
        SELECT p.id, p.document_id, p.purchase_date AS event_date,
               COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS designation,
               p.quantity, COALESCE(p.unit, r.unit, 'kg') AS unit, p.unit_price, p.total, p.notes
        FROM purchases p
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.supplier_id = %s
        ORDER BY p.purchase_date DESC, p.id DESC
        """,
        (supplier_id,),
    )
    total_amount = sum(float(item["total"]) for item in purchases_rows)
    return {
        "supplier": supplier,
        "purchases": purchases_rows,
        "purchase_count": len(purchases_rows),
        "total_amount": total_amount,
    }
