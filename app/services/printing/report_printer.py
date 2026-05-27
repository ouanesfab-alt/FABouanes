"""Sale document payload building (finished, raw, grouped documents, payments)."""

from __future__ import annotations

from typing import Any

from app.core.db_access import query_db

from .base import _payment_mode_label, _print_defaults


def _sale_line_to_doc_line(row, item_name: str) -> dict[str, Any]:
    return {
        "item_name": item_name,
        "quantity": row["quantity"],
        "unit": row["unit"],
        "unit_price": row["unit_price"],
        "total": row["total"],
    }


def _sale_document_subtitle(lines: list[dict[str, Any]]) -> str:
    kinds = {str(line.get("kind") or "") for line in lines}
    if kinds == {"finished"}:
        return "Vente produit final"
    if kinds == {"raw"}:
        return "Vente matière première"
    return "Vente multi-produits"


def _build_sale_finished_payload(item_id: int, *, _build_print_payload) -> dict[str, Any] | None:
    pointer = query_db("SELECT id, document_id FROM sales WHERE id = %s", (item_id,), one=True)
    if pointer and pointer["document_id"]:
        return _build_print_payload("sale_document", int(pointer["document_id"]))
    row = query_db(
        """
        SELECT s.*, f.name AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM sales s
        JOIN finished_products f ON f.id = s.finished_product_id
        LEFT JOIN clients c ON c.id = s.client_id
        WHERE s.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not row:
        return None
    lines = [_sale_line_to_doc_line(row, row["item_name"])]
    return _print_defaults({
        "title": "Facture",
        "subtitle": "Vente produit final",
        "number": f"VPF-{row['id']:06d}",
        "date": row["sale_date"],
        "partner_label": "Client",
        "partner_name": row["partner_name"],
        "partner_phone": row["partner_phone"] or "",
        "partner_address": row["partner_address"] or "",
        "payment_mode": _payment_mode_label(row["sale_type"]),
        "item_label": "Article",
        "item_name": row["item_name"],
        "quantity": row["quantity"],
        "unit": row["unit"],
        "unit_price": row["unit_price"],
        "total": row["total"],
        "paid": row["amount_paid"],
        "due": row["balance_due"],
        "notes": row["notes"] or "",
        "lines": lines,
    })


def _build_sale_raw_payload(item_id: int, *, _build_print_payload) -> dict[str, Any] | None:
    pointer = query_db("SELECT id, document_id FROM raw_sales WHERE id = %s", (item_id,), one=True)
    if pointer and pointer["document_id"]:
        return _build_print_payload("sale_document", int(pointer["document_id"]))
    row = query_db(
        """
        SELECT rs.*, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM raw_sales rs
        JOIN raw_materials r ON r.id = rs.raw_material_id
        LEFT JOIN clients c ON c.id = rs.client_id
        WHERE rs.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not row:
        return None
    lines = [_sale_line_to_doc_line(row, row["item_name"])]
    return _print_defaults({
        "title": "Facture",
        "subtitle": "Vente matière première",
        "number": f"VMP-{row['id']:06d}",
        "date": row["sale_date"],
        "partner_label": "Client",
        "partner_name": row["partner_name"],
        "partner_phone": row["partner_phone"] or "",
        "partner_address": row["partner_address"] or "",
        "payment_mode": _payment_mode_label(row["sale_type"]),
        "item_label": "Article",
        "item_name": row["item_name"],
        "quantity": row["quantity"],
        "unit": row["unit"],
        "unit_price": row["unit_price"],
        "total": row["total"],
        "paid": row["amount_paid"],
        "due": row["balance_due"],
        "notes": row["notes"] or "",
        "lines": lines,
    })


def _build_sale_document_payload(item_id: int) -> dict[str, Any] | None:
    doc = query_db(
        """
        SELECT sd.*, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM sale_documents sd
        LEFT JOIN clients c ON c.id = sd.client_id
        WHERE sd.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not doc:
        return None
    line_rows = query_db(
        """
        SELECT * FROM (
            SELECT 'finished' AS kind, s.id AS line_id, s.quantity, s.unit, s.unit_price, s.total, f.name AS item_name
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.document_id = %s
            UNION ALL
            SELECT 'raw' AS kind, rs.id AS line_id, rs.quantity, rs.unit, rs.unit_price, rs.total, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.document_id = %s
        ) lines
        ORDER BY line_id ASC
        """,
        (item_id, item_id),
    )
    if not line_rows:
        return None
    lines = [_sale_line_to_doc_line(row, row["item_name"]) | {"kind": row["kind"]} for row in line_rows]
    subtitle = _sale_document_subtitle(lines)
    clean_lines = [{k: v for k, v in line.items() if k != "kind"} for line in lines]
    return _print_defaults({
        "title": "Facture",
        "subtitle": subtitle,
        "number": f"FAC-{doc['id']:06d}",
        "date": doc["sale_date"],
        "partner_label": "Client",
        "partner_name": doc["partner_name"],
        "partner_phone": doc["partner_phone"] or "",
        "partner_address": doc["partner_address"] or "",
        "payment_mode": _payment_mode_label(doc["sale_type"]),
        "item_label": "Article",
        "item_name": f"{len(clean_lines)} ligne(s)",
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": doc["total"],
        "paid": doc["amount_paid"],
        "due": doc["balance_due"],
        "notes": doc["notes"] or "",
        "lines": clean_lines,
    })


def _build_payment_payload(item_id: int) -> dict[str, Any] | None:
    row = query_db(
        """
        SELECT p.*, c.name AS partner_name, c.phone AS partner_phone, c.address AS partner_address
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        WHERE p.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not row:
        return None
    label = "Avance client" if row["payment_type"] == "avance" else "Versement client"
    lines = [
        {
            "item_name": label,
            "quantity": None,
            "unit": "",
            "unit_price": None,
            "total": row["amount"],
        }
    ]
    return _print_defaults({
        "title": "Re\u00e7u",
        "subtitle": label,
        "number": f"PAY-{row['id']:06d}",
        "date": row["payment_date"],
        "partner_label": "Client",
        "partner_name": row["partner_name"],
        "partner_phone": row["partner_phone"] or "",
        "partner_address": row["partner_address"] or "",
        "payment_mode": _payment_mode_label(row["payment_type"]),
        "item_label": "Reference",
        "item_name": label,
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": row["amount"],
        "paid": row["amount"],
        "due": 0,
        "notes": row["notes"] or "",
        "lines": lines,
    })
