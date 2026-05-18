from __future__ import annotations

import json
from typing import Any

from app.core.db_access import db_transaction, execute_db, query_db
from app.services.stock_service import recalc_sale_document_totals


def client_balance(client_id: int) -> float:
    row = query_db(
        """
        SELECT c.opening_credit
             + COALESCE((SELECT SUM(total) FROM sales WHERE client_id = c.id AND sale_type = 'credit'), 0)
             + COALESCE((SELECT SUM(total) FROM raw_sales WHERE client_id = c.id AND sale_type = 'credit'), 0)
             - COALESCE((SELECT SUM(amount) FROM payments WHERE client_id = c.id AND payment_type = 'versement'), 0)
             + COALESCE((SELECT SUM(amount) FROM payments WHERE client_id = c.id AND payment_type = 'avance'), 0) AS balance
        FROM clients c
        WHERE c.id = %s
        """,
        (client_id,),
        one=True,
    )
    return float(row["balance"]) if row else 0.0


def get_open_credit_entries(client_id: int | None = None):
    params: list[Any] = []
    where_sales = "WHERE s.balance_due > 0"
    where_raw = "WHERE rs.balance_due > 0"
    if client_id is not None:
        where_sales += " AND s.client_id = %s"
        where_raw += " AND rs.client_id = %s"
        params.append(client_id)
        params.append(client_id)
    return query_db(
        f"""
        SELECT * FROM (
            SELECT 'finished' AS item_kind, s.id, s.client_id, c.name AS client_name, f.name AS item_name,
                   s.balance_due, s.sale_date, s.total
            FROM sales s
            JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            {where_sales}
            UNION ALL
            SELECT 'raw' AS item_kind, rs.id, rs.client_id, c.name AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                   rs.balance_due, rs.sale_date, rs.total
            FROM raw_sales rs
            JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            {where_raw}
        ) x
        ORDER BY sale_date ASC, id ASC
        """,
        tuple(params),
    )


def apply_payment_to_entry(kind: str, row_id: int, amount: float) -> float:
    if amount <= 0:
        return 0.0
    if kind == "finished":
        sale = query_db("SELECT balance_due, document_id FROM sales WHERE id = %s", (row_id,), one=True)
        if not sale:
            return 0.0
        paid = min(amount, float(sale["balance_due"]))
        execute_db("UPDATE sales SET balance_due = balance_due - ?, amount_paid = amount_paid + ? WHERE id = %s", (paid, paid, row_id))
        recalc_sale_document_totals(int(sale["document_id"])) if sale["document_id"] else None
        return paid
    sale = query_db("SELECT balance_due, document_id FROM raw_sales WHERE id = %s", (row_id,), one=True)
    if not sale:
        return 0.0
    paid = min(amount, float(sale["balance_due"]))
    execute_db("UPDATE raw_sales SET balance_due = balance_due - ?, amount_paid = amount_paid + ? WHERE id = %s", (paid, paid, row_id))
    recalc_sale_document_totals(int(sale["document_id"])) if sale["document_id"] else None
    return paid


def reverse_payment_allocations(payment_row) -> None:
    with db_transaction():
        meta_raw = payment_row["allocation_meta"] if "allocation_meta" in payment_row.keys() else None
        if meta_raw:
            try:
                allocations = json.loads(meta_raw)
            except Exception:
                allocations = []
            for allocation in allocations:
                kind = allocation.get("kind")
                row_id = int(allocation.get("id"))
                amount = float(allocation.get("amount", 0) or 0)
                if amount <= 0:
                    continue
                if kind == "finished":
                    doc_row = query_db("SELECT document_id FROM sales WHERE id = %s", (row_id,), one=True)
                    execute_db("UPDATE sales SET amount_paid = amount_paid - ?, balance_due = balance_due + ? WHERE id = %s", (amount, amount, row_id))
                    recalc_sale_document_totals(int(doc_row["document_id"])) if doc_row and doc_row["document_id"] else None
                elif kind == "raw":
                    doc_row = query_db("SELECT document_id FROM raw_sales WHERE id = %s", (row_id,), one=True)
                    execute_db("UPDATE raw_sales SET amount_paid = amount_paid - ?, balance_due = balance_due + ? WHERE id = %s", (amount, amount, row_id))
                    recalc_sale_document_totals(int(doc_row["document_id"])) if doc_row and doc_row["document_id"] else None
            return
        if payment_row["payment_type"] != "versement":
            return
        if payment_row["sale_kind"] == "finished" and payment_row["sale_id"]:
            doc_row = query_db("SELECT document_id FROM sales WHERE id = %s", (payment_row["sale_id"],), one=True)
            execute_db("UPDATE sales SET amount_paid = amount_paid - ?, balance_due = balance_due + ? WHERE id = %s", (payment_row["amount"], payment_row["amount"], payment_row["sale_id"]))
            recalc_sale_document_totals(int(doc_row["document_id"])) if doc_row and doc_row["document_id"] else None
        elif payment_row["sale_kind"] == "raw" and payment_row["raw_sale_id"]:
            doc_row = query_db("SELECT document_id FROM raw_sales WHERE id = %s", (payment_row["raw_sale_id"],), one=True)
            execute_db("UPDATE raw_sales SET amount_paid = amount_paid - ?, balance_due = balance_due + ? WHERE id = %s", (payment_row["amount"], payment_row["amount"], payment_row["raw_sale_id"]))
            recalc_sale_document_totals(int(doc_row["document_id"])) if doc_row and doc_row["document_id"] else None


def create_payment_record(client_id: int, amount: float, payment_date: str, notes: str, sale_link: str = "", payment_type: str = "versement") -> int:
    if amount <= 0:
        raise ValueError("Le montant doit etre superieur a zero.")
    with db_transaction():
        client = query_db("SELECT id FROM clients WHERE id = %s", (client_id,), one=True)
        if not client:
            raise ValueError("Client introuvable.")
        if payment_type == "avance":
            return execute_db(
                """
                INSERT INTO payments (client_id, sale_id, raw_sale_id, sale_kind, payment_type, allocation_meta, amount, payment_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (client_id, None, None, None, "avance", None, amount, payment_date, notes or "Avance client"),
            )

        sale_id = None
        raw_sale_id = None
        sale_kind = None
        allocations: list[dict[str, Any]] = []
        applied = 0.0
        if sale_link and ":" in sale_link:
            sale_kind, id_str = sale_link.split(":", 1)
            row_id = int(id_str)
            entry = query_db(
                "SELECT client_id FROM sales WHERE id = %s" if sale_kind == "finished" else "SELECT client_id FROM raw_sales WHERE id = %s",
                (row_id,),
                one=True,
            )
            if entry and int(entry["client_id"] or 0) != client_id:
                raise ValueError("Cette creance ne correspond pas au client choisi.")
            applied = apply_payment_to_entry(sale_kind, row_id, amount)
            if applied <= 0:
                raise ValueError("Aucune creance ouverte a solder pour ce client.")
            allocations = [{"kind": sale_kind, "id": row_id, "amount": applied}]
            if sale_kind == "finished":
                sale_id = row_id
            else:
                raw_sale_id = row_id
        else:
            remaining = amount
            for entry in get_open_credit_entries(client_id):
                if remaining <= 0:
                    break
                paid = apply_payment_to_entry(entry["item_kind"], entry["id"], remaining)
                if paid > 0:
                    allocations.append({"kind": entry["item_kind"], "id": int(entry["id"]), "amount": paid})
                    applied += paid
                    remaining -= paid
            if applied <= 0 and client_balance(client_id) <= 0:
                raise ValueError("Aucune dette ouverte pour ce client.")

        return execute_db(
            """
            INSERT INTO payments (client_id, sale_id, raw_sale_id, sale_kind, payment_type, allocation_meta, amount, payment_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (client_id, sale_id, raw_sale_id, sale_kind, "versement", json.dumps(allocations) if allocations else None, amount, payment_date, notes or "Versement client"),
        )
