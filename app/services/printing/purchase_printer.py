"""Purchase / bon de commande payload building."""

from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
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


async def _build_purchase_payload(
    item_id: int,
    *,
    _build_print_payload,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Build payload for a single purchase row.

    ``_build_print_payload`` is injected to avoid circular imports (the top-level
    dispatcher lives in ``__init__``).
    """
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_purchase_payload_impl(item_id, _build_print_payload, session)
    return await _build_purchase_payload_impl(item_id, _build_print_payload, db)


async def _build_purchase_payload_impl(
    item_id: int,
    _build_print_payload,
    db: AsyncSession,
) -> dict[str, Any] | None:
    pointer_res = await db.execute(
        text("SELECT id, document_id FROM purchases WHERE id = :item_id"),
        {"item_id": item_id},
    )
    pointer = pointer_res.first()
    if pointer and pointer.document_id:
        return await _build_print_payload("purchase_document", int(pointer.document_id), db=db)

    row_res = await db.execute(
        text("""
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
                    WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) LIKE 'sac%' THEN p.quantity / CAST(COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50') AS NUMERIC)
                    WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                    ELSE p.quantity
                END AS display_quantity,
                CASE
                    WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) LIKE 'sac%' THEN p.unit_price * CAST(COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50') AS NUMERIC)
                    WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                    ELSE p.unit_price
                END AS display_unit_price,
               s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
         FROM purchases p
         LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
         LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
         LEFT JOIN suppliers s ON s.id = p.supplier_id
         WHERE p.id = :item_id
        """),
        {"item_id": item_id},
    )
    row = row_res.first()
    if not row:
        return None

    row_dict = dict(row._mapping)
    lines = [_purchase_line_to_doc_line(row_dict)]
    return _print_defaults({
        "title": "Bon d'achat",
        "subtitle": "Achat matière première",
        "number": f"ACH-{row_dict['id']:06d}",
        "date": row_dict["purchase_date"],
        "partner_label": "Fournisseur",
        "partner_name": row_dict["partner_name"] or "Non renseigné",
        "partner_phone": row_dict["partner_phone"] or "",
        "partner_address": row_dict["partner_address"] or "",
        "item_label": "Matière",
        "item_name": row_dict["item_name"],
        "quantity": row_dict["display_quantity"],
        "unit": row_dict["display_unit"],
        "unit_price": row_dict["display_unit_price"],
        "total": row_dict["total"],
        "paid": None,
        "due": None,
        "notes": row_dict["notes"] or "",
        "lines": lines,
    })


async def _build_purchase_document_payload(
    item_id: int,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Build payload for a grouped purchase document."""
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_purchase_document_payload_impl(item_id, session)
    return await _build_purchase_document_payload_impl(item_id, db)


async def _build_purchase_document_payload_impl(
    item_id: int,
    db: AsyncSession,
) -> dict[str, Any] | None:
    doc_res = await db.execute(
        text("""
        SELECT pd.*, s.name AS partner_name, s.phone AS partner_phone, s.address AS partner_address
        FROM purchase_documents pd
        LEFT JOIN suppliers s ON s.id = pd.supplier_id
        WHERE pd.id = :item_id
        """),
        {"item_id": item_id},
    )
    doc = doc_res.first()
    if not doc:
        return None

    doc_dict = dict(doc._mapping)
    line_rows_res = await db.execute(
        text("""
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
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) LIKE 'sac%' THEN p.quantity / CAST(COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50') AS NUMERIC)
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                   ELSE p.quantity
               END AS display_quantity,
               CASE
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) LIKE 'sac%' THEN p.unit_price * CAST(COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50') AS NUMERIC)
                   WHEN lower(COALESCE(p.unit, fp.default_unit, rm.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                   ELSE p.unit_price
               END AS display_unit_price
        FROM purchases p
        LEFT JOIN raw_materials rm ON rm.id = p.raw_material_id
        LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
        WHERE p.document_id = :item_id
        ORDER BY p.id ASC
        """),
        {"item_id": item_id},
    )
    line_rows = line_rows_res.all()
    if not line_rows:
        return None
    lines = [_purchase_line_to_doc_line(dict(row._mapping)) for row in line_rows]
    return _print_defaults({
        "title": "Bon d'achat",
        "subtitle": "Achat multi-produits",
        "number": f"ACH-{doc_dict['id']:06d}",
        "date": doc_dict["purchase_date"],
        "partner_label": "Fournisseur",
        "partner_name": doc_dict["partner_name"] or "Non renseigné",
        "partner_phone": doc_dict["partner_phone"] or "",
        "partner_address": doc_dict["partner_address"] or "",
        "item_label": "Matière",
        "item_name": f"{len(lines)} ligne(s)",
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": doc_dict["total"],
        "paid": None,
        "due": None,
        "notes": doc_dict["notes"] or "",
        "lines": lines,
    })
