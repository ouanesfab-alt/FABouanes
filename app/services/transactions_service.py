from __future__ import annotations

from app.utils.pagination import paginate_sequence
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import execute_db, query_db
from app.core.storage import backup_database


def transactions_context(
    filter_type: str = "all",
    filter_name: str = "",
    filter_date: str = "",
    filter_operation: str = "",
    args=None,
    path: str = "/operations",
) -> dict:
    rows = query_db(
        """
        SELECT * FROM (
            SELECT 'Achat' AS tx_type, 'purchase' AS tx_kind, p.id, p.purchase_date AS tx_date,
                   COALESCE(s.name, '-') AS partner_name, r.name AS designation,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS quantity,
                   COALESCE(p.unit, r.unit, 'kg') AS unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS unit_price,
                   p.total, CAST(NULL AS numeric) AS paid, CAST(NULL AS numeric) AS due, p.document_id AS document_id, p.created_at AS tx_created_at
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            JOIN raw_materials r ON r.id = p.raw_material_id
            UNION ALL
            SELECT 'Vente' AS tx_type,
                   CASE WHEN x.row_kind='finished' THEN 'sale_finished' ELSE 'sale_raw' END AS tx_kind,
                   x.id, x.sale_date AS tx_date, COALESCE(x.client_name, '-') AS partner_name, x.item_name AS designation,
                   x.quantity, x.unit, x.unit_price, x.total, x.amount_paid AS paid, x.balance_due AS due, x.document_id AS document_id, x.created_at AS tx_created_at
            FROM (
                SELECT s.id, s.document_id, 'finished' AS row_kind, s.sale_date, c.name AS client_name, f.name AS item_name, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due, s.created_at
                FROM sales s LEFT JOIN clients c ON c.id = s.client_id JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT rs.id, rs.document_id, 'raw' AS row_kind, rs.sale_date, c.name AS client_name, r.name AS item_name, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due, rs.created_at
                FROM raw_sales rs LEFT JOIN clients c ON c.id = rs.client_id JOIN raw_materials r ON r.id = rs.raw_material_id
            ) x
            UNION ALL
            SELECT CASE WHEN p.payment_type='avance' THEN 'Avance' ELSE 'Versement' END AS tx_type, 'payment' AS tx_kind, p.id, p.payment_date AS tx_date,
                   c.name AS partner_name,
                   CASE
                       WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Versement vente #' || CAST(p.sale_id AS VARCHAR)
                       WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Versement vente matiere #' || CAST(p.raw_sale_id AS VARCHAR)
                       ELSE CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END
                   END AS designation,
                   CAST(NULL AS numeric) AS quantity, CAST(NULL AS varchar) AS unit, CAST(NULL AS numeric) AS unit_price, p.amount AS total, p.amount AS paid, CAST(NULL AS numeric) AS due, CAST(NULL AS integer) AS document_id, p.created_at AS tx_created_at
            FROM payments p JOIN clients c ON c.id = p.client_id
        ) t
        ORDER BY tx_date DESC, tx_created_at DESC, id DESC
        """
    )
    name_filter = (filter_name or "").strip().lower()
    date_filter = (filter_date or "").strip()
    operation_filter = (filter_operation or "").strip().lower()
    filtered = []
    for row in rows:
        if filter_type == "purchase" and row["tx_type"] != "Achat":
            continue
        if filter_type == "sale" and row["tx_type"] != "Vente":
            continue
        if filter_type == "payment" and row["tx_kind"] != "payment":
            continue
        if name_filter and name_filter not in f"{row['partner_name']} {row['designation']}".lower():
            continue
        if date_filter and str(row["tx_date"]) != date_filter:
            continue
        if operation_filter and operation_filter not in str(row["tx_type"]).lower():
            continue
        
        row_dict = dict(row)
        tx_created = row_dict.get("tx_created_at")
        if hasattr(tx_created, "strftime"):
            row_dict["tx_time"] = tx_created.strftime("%H:%M")
        elif isinstance(tx_created, str):
            row_dict["tx_time"] = tx_created.split()[1][:5] if " " in tx_created else ""
        else:
            row_dict["tx_time"] = ""
        filtered.append(row_dict)
        
    page_rows, pagination = paginate_sequence(filtered, args or {}, path)
    return {
        "transactions": page_rows,
        "filter_type": filter_type,
        "filter_name": filter_name,
        "filter_date": filter_date,
        "filter_operation": filter_operation,
        "pagination": pagination,
    }


def update_production_notes(batch_id: int, production_date: str, notes: str) -> None:
    if not batch_id:
        raise ValueError("Identifiant manquant.")
    before = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
    if not before:
        raise ValueError("Production introuvable.")
    updates = {}
    if production_date:
        updates["production_date"] = production_date
    updates["notes"] = notes
    sets = ", ".join(f"{key}=%s" for key in updates)
    values = list(updates.values()) + [batch_id]
    execute_db(f"UPDATE production_batches SET {sets} WHERE id = %s", tuple(values))
    after = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
    log_activity("edit_production_notes", "production", batch_id, f"date={production_date}")
    audit_event("edit_production_notes", "production", batch_id, before=before, after=after)
    backup_database("edit_production_notes")
