"""Sale document payload building (finished, raw, grouped documents, payments)."""

from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
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


async def _build_sale_finished_payload(
    item_id: int,
    *,
    _build_print_payload,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_sale_finished_payload_impl(item_id, _build_print_payload, session)
    return await _build_sale_finished_payload_impl(item_id, _build_print_payload, db)


async def _build_sale_finished_payload_impl(
    item_id: int,
    _build_print_payload,
    db: AsyncSession,
) -> dict[str, Any] | None:
    pointer_res = await db.execute(
        text("SELECT id, document_id FROM sales WHERE id = :item_id"),
        {"item_id": item_id},
    )
    pointer = pointer_res.first()
    if pointer and pointer.document_id:
        return await _build_print_payload("sale_document", int(pointer.document_id), db=db)
        
    row_res = await db.execute(
        text("""
        SELECT s.*, f.name AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM sales s
        JOIN finished_products f ON f.id = s.finished_product_id
        LEFT JOIN clients c ON c.id = s.client_id
        WHERE s.id = :item_id
        """),
        {"item_id": item_id},
    )
    row = row_res.first()
    if not row:
        return None
        
    row_dict = dict(row._mapping)
    lines = [_sale_line_to_doc_line(row_dict, row_dict["item_name"])]
    return _print_defaults({
        "title": "Facture",
        "subtitle": "Vente produit final",
        "number": f"VPF-{row_dict['id']:06d}",
        "date": row_dict["sale_date"],
        "partner_label": "Client",
        "partner_name": row_dict["partner_name"],
        "partner_phone": row_dict["partner_phone"] or "",
        "partner_address": row_dict["partner_address"] or "",
        "payment_mode": _payment_mode_label(row_dict["sale_type"]),
        "item_label": "Article",
        "item_name": row_dict["item_name"],
        "quantity": row_dict["quantity"],
        "unit": row_dict["unit"],
        "unit_price": row_dict["unit_price"],
        "total": row_dict["total"],
        "paid": row_dict["amount_paid"],
        "due": row_dict["balance_due"],
        "notes": row_dict["notes"] or "",
        "lines": lines,
    })


async def _build_sale_raw_payload(
    item_id: int,
    *,
    _build_print_payload,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_sale_raw_payload_impl(item_id, _build_print_payload, session)
    return await _build_sale_raw_payload_impl(item_id, _build_print_payload, db)


async def _build_sale_raw_payload_impl(
    item_id: int,
    _build_print_payload,
    db: AsyncSession,
) -> dict[str, Any] | None:
    pointer_res = await db.execute(
        text("SELECT id, document_id FROM raw_sales WHERE id = :item_id"),
        {"item_id": item_id},
    )
    pointer = pointer_res.first()
    if pointer and pointer.document_id:
        return await _build_print_payload("sale_document", int(pointer.document_id), db=db)
        
    row_res = await db.execute(
        text("""
        SELECT rs.*, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM raw_sales rs
        JOIN raw_materials r ON r.id = rs.raw_material_id
        LEFT JOIN clients c ON c.id = rs.client_id
        WHERE rs.id = :item_id
        """),
        {"item_id": item_id},
    )
    row = row_res.first()
    if not row:
        return None
        
    row_dict = dict(row._mapping)
    lines = [_sale_line_to_doc_line(row_dict, row_dict["item_name"])]
    return _print_defaults({
        "title": "Facture",
        "subtitle": "Vente matière première",
        "number": f"VMP-{row_dict['id']:06d}",
        "date": row_dict["sale_date"],
        "partner_label": "Client",
        "partner_name": row_dict["partner_name"],
        "partner_phone": row_dict["partner_phone"] or "",
        "partner_address": row_dict["partner_address"] or "",
        "payment_mode": _payment_mode_label(row_dict["sale_type"]),
        "item_label": "Article",
        "item_name": row_dict["item_name"],
        "quantity": row_dict["quantity"],
        "unit": row_dict["unit"],
        "unit_price": row_dict["unit_price"],
        "total": row_dict["total"],
        "paid": row_dict["amount_paid"],
        "due": row_dict["balance_due"],
        "notes": row_dict["notes"] or "",
        "lines": lines,
    })


async def _build_sale_document_payload(
    item_id: int,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_sale_document_payload_impl(item_id, session)
    return await _build_sale_document_payload_impl(item_id, db)


async def _build_sale_document_payload_impl(
    item_id: int,
    db: AsyncSession,
) -> dict[str, Any] | None:
    doc_res = await db.execute(
        text("""
        SELECT sd.*, COALESCE(c.name, 'Comptoir') AS partner_name,
               c.phone AS partner_phone, c.address AS partner_address
        FROM sale_documents sd
        LEFT JOIN clients c ON c.id = sd.client_id
        WHERE sd.id = :item_id
        """),
        {"item_id": item_id},
    )
    doc = doc_res.first()
    if not doc:
        return None
        
    doc_dict = dict(doc._mapping)
    line_rows_res = await db.execute(
        text("""
        SELECT * FROM (
            SELECT 'finished' AS kind, s.id AS line_id, s.quantity, s.unit, s.unit_price, s.total, f.name AS item_name
            FROM sales s
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.document_id = :item_id
            UNION ALL
            SELECT 'raw' AS kind, rs.id AS line_id, rs.quantity, rs.unit, rs.unit_price, rs.total, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name
            FROM raw_sales rs
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.document_id = :item_id
        ) lines
        ORDER BY line_id ASC
        """),
        {"item_id": item_id},
    )
    line_rows = line_rows_res.all()
    if not line_rows:
        return None
    lines = [_sale_line_to_doc_line(dict(row._mapping), row.item_name) | {"kind": row.kind} for row in line_rows]
    subtitle = _sale_document_subtitle(lines)
    clean_lines = [{k: v for k, v in line.items() if k != "kind"} for line in lines]
    return _print_defaults({
        "title": "Facture",
        "subtitle": subtitle,
        "number": f"FAC-{doc_dict['id']:06d}",
        "date": doc_dict["sale_date"],
        "partner_label": "Client",
        "partner_name": doc_dict["partner_name"],
        "partner_phone": doc_dict["partner_phone"] or "",
        "partner_address": doc_dict["partner_address"] or "",
        "payment_mode": _payment_mode_label(doc_dict["sale_type"]),
        "item_label": "Article",
        "item_name": f"{len(clean_lines)} ligne(s)",
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": doc_dict["total"],
        "paid": doc_dict["amount_paid"],
        "due": doc_dict["balance_due"],
        "notes": doc_dict["notes"] or "",
        "lines": clean_lines,
    })


async def _build_payment_payload(
    item_id: int,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_payment_payload_impl(item_id, session)
    return await _build_payment_payload_impl(item_id, db)


async def _build_payment_payload_impl(
    item_id: int,
    db: AsyncSession,
) -> dict[str, Any] | None:
    row_res = await db.execute(
        text("""
        SELECT p.*, c.name AS partner_name, c.phone AS partner_phone, c.address AS partner_address
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        WHERE p.id = :item_id
        """),
        {"item_id": item_id},
    )
    row = row_res.first()
    if not row:
        return None
        
    row_dict = dict(row._mapping)
    label = "Avance client" if row_dict["payment_type"] == "avance" else "Versement client"
    lines = [
        {
            "item_name": label,
            "quantity": None,
            "unit": "",
            "unit_price": None,
            "total": row_dict["amount"],
        }
    ]
    return _print_defaults({
        "title": "Re\u00e7u",
        "subtitle": label,
        "number": f"PAY-{row_dict['id']:06d}",
        "date": row_dict["payment_date"],
        "partner_label": "Client",
        "partner_name": row_dict["partner_name"],
        "partner_phone": row_dict["partner_phone"] or "",
        "partner_address": row_dict["partner_address"] or "",
        "payment_mode": _payment_mode_label(row_dict["payment_type"]),
        "item_label": "Reference",
        "item_name": label,
        "quantity": None,
        "unit": "",
        "unit_price": None,
        "total": row_dict["amount"],
        "paid": row_dict["amount"],
        "due": 0,
        "notes": row_dict["notes"] or "",
        "lines": lines,
    })
