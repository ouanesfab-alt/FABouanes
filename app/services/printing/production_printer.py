"""Production-related document payload building."""

from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from .base import _print_defaults


async def _build_production_payload(
    item_id: int,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _build_production_payload_impl(item_id, session)
    return await _build_production_payload_impl(item_id, db)


async def _build_production_payload_impl(
    item_id: int,
    db: AsyncSession,
) -> dict[str, Any] | None:
    row_res = await db.execute(
        text("""
        SELECT pb.*, fp.name AS item_name
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        WHERE pb.id = :item_id
        """),
        {"item_id": item_id},
    )
    row = row_res.first()
    if not row:
        return None

    row_dict = dict(row._mapping)
    item_rows_res = await db.execute(
        text("""
        SELECT r.name AS material_name, pbi.quantity, r.unit, pbi.unit_cost_snapshot, pbi.line_cost
        FROM production_batch_items pbi
        JOIN raw_materials r ON r.id = pbi.raw_material_id
        WHERE pbi.batch_id = :item_id
        ORDER BY pbi.id ASC
        """),
        {"item_id": item_id},
    )
    item_rows = [dict(r._mapping) for r in item_rows_res.all()]
    recipe_text = " + ".join(
        f"{item['material_name']} {item['quantity']} {item['unit'] or 'kg'}" for item in item_rows
    ) or "-"
    lines = [
        {
            "item_name": item["material_name"],
            "quantity": item["quantity"],
            "unit": item["unit"] or "kg",
            "unit_price": item["unit_cost_snapshot"],
            "total": item["line_cost"],
        }
        for item in item_rows
    ]
    if not lines:
        lines = [
            {
                "item_name": row_dict["item_name"],
                "quantity": row_dict["output_quantity"],
                "unit": "kg",
                "unit_price": row_dict["unit_cost"],
                "total": row_dict["production_cost"],
            }
        ]
    return _print_defaults({
        "title": "Fiche de production",
        "subtitle": "Production enregistree",
        "number": f"PROD-{row_dict['id']:06d}",
        "date": row_dict["production_date"],
        "partner_label": "Produit final",
        "partner_name": row_dict["item_name"],
        "item_label": "Recette",
        "item_name": recipe_text,
        "quantity": row_dict["output_quantity"],
        "unit": "kg",
        "unit_price": row_dict["unit_cost"],
        "total": row_dict["production_cost"],
        "paid": None,
        "due": None,
        "notes": row_dict["notes"] or "",
        "lines": lines,
    })
