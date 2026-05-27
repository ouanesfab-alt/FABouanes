"""Purchase / bon de commande payload building."""

from __future__ import annotations

from typing import Any

from app.core.db_access import query_db

from .base import _print_defaults


def _purchase_line_to_doc_line(row) -> dict[str, Any]:
    unit = row["display_unit"] or row["base_unit"] or "kg"
    return {
        "item_name": row["item_name"],
        "quantity": row["display_quantity"],
        "unit": unit,
        "unit_price": row["display_unit_price"],
        "total": row["total"],
    }


def _build_purchase_payload(item_id: int, *, _build_print_payload) -> dict[str, Any] | None:
    """Build payload for a single purchase row.

    ``_build_print_payload`` is injected to avoid circular imports (the top-level
    dispatcher lives in ``__init__``).
    """
    pointer = query_db("SELECT id, document_id FROM purchases WHERE id = %s", (item_id,), one=True)
    if pointer and pointer["document_id"]:
        return _build_print_payload("purchase_document", int(pointer["document_id"]))
    row = query_db(
        """
        SELECT p.*, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN fp.name
                   ELSE COALESCE(NULLIF(p.custom_item_name, ''), rm.name)
               END AS item_name, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN fp.default_unit
                   ELSE rm.unit
               END AS base_unit, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                   ELSE COALESCE(p.unit, rm.unit, 'kg')
               END AS display_unit,
               CASE
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                   ELSE p.quantity
               END AS display_quantity,
               CASE
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                   ELSE p.unit_price
               END AS display_unit_price,
               s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
        FROM purchases p
        LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
        LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not row:
        return None
    lines = [_purchase_line_to_doc_line(row)]
    return _print_defaults({
        "title": "Bon d'achat",
        "subtitle": "Achat matière première",
        "number": f"ACH-{row['id']:06d}",
        "date": row["purchase_date"],
        "partner_label": "Fournisseur",
        "partner_name": row["partner_name"] or "Non renseigné",
        "partner_phone": row["partner_phone"] or "",
        "partner_address": row["partner_address"] or "",
        "item_label": "Matière",
        "item_name": row["item_name"],
        "quantity": row["display_quantity"],
        "unit": row["display_unit"],
        "unit_price": row["display_unit_price"],
        "total": row["total"],
        "paid": None,
        "due": None,
        "notes": row["notes"] or "",
        "lines": lines,
    })


def _build_purchase_document_payload(item_id: int) -> dict[str, Any] | None:
    """Build payload for a grouped purchase document."""
    doc = query_db(
        """
        SELECT pd.*, s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
        FROM purchase_documents pd
        LEFT JOIN suppliers s ON s.id = pd.supplier_id
        WHERE pd.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not doc:
        return None
    line_rows = query_db(
        """
        SELECT p.*, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN fp.name
                   ELSE COALESCE(NULLIF(p.custom_item_name, ''), rm.name)
               END AS item_name, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN fp.default_unit
                   ELSE rm.unit
               END AS base_unit, 
               CASE 
                   WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                   ELSE COALESCE(p.unit, rm.unit, 'kg')
               END AS display_unit,
               CASE
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                   ELSE p.quantity
               END AS display_quantity,
               CASE
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                   ELSE p.unit_price
               END AS display_unit_price
        FROM purchases p
        LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
        LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
        WHERE p.document_id = %s
        ORDER BY p.id ASC
        """,
        (item_id,),
    )
    if not line_rows:
        return None
    lines = [_purchase_line_to_doc_line(row) for row in line_rows]
    return _print_defaults({
        "title": "Bon d'achat",
        "subtitle": "Achat multi-produits",
        "number": f"ACH-{doc['id']:06d}",
        "date": doc["purchase_date"],
        "partner_label": "Fournisseur",
        "partner_name": doc["partner_name"] or "Non renseigné",
        "partner_phone": doc["partner_phone"] or "",
        "partner_address": doc["partner_address"] or "",
        "item_label": "Matière",
        "item_name": f"{len(lines)} ligne(s)",
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": doc["total"],
        "paid": None,
        "due": None,
        "notes": doc["notes"] or "",
        "lines": lines,
    })
