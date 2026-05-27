"""Production-related document payload building."""

from __future__ import annotations

from typing import Any

from app.core.db_access import query_db

from .base import _print_defaults


def _build_production_payload(item_id: int) -> dict[str, Any] | None:
    row = query_db(
        """
        SELECT pb.*, fp.name AS item_name
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        WHERE pb.id = %s
        """,
        (item_id,),
        one=True,
    )
    if not row:
        return None
    item_rows = query_db(
        """
        SELECT r.name AS material_name, pbi.quantity, r.unit, pbi.unit_cost_snapshot, pbi.line_cost
        FROM production_batch_items pbi
        JOIN raw_materials r ON r.id = pbi.raw_material_id
        WHERE pbi.batch_id = %s
        ORDER BY pbi.id ASC
        """,
        (item_id,),
    )
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
                "item_name": row["item_name"],
                "quantity": row["output_quantity"],
                "unit": "kg",
                "unit_price": row["unit_cost"],
                "total": row["production_cost"],
            }
        ]
    return _print_defaults({
        "title": "Fiche de production",
        "subtitle": "Production enregistree",
        "number": f"PROD-{row['id']:06d}",
        "date": row["production_date"],
        "partner_label": "Produit final",
        "partner_name": row["item_name"],
        "item_label": "Recette",
        "item_name": recipe_text,
        "quantity": row["output_quantity"],
        "unit": "kg",
        "unit_price": row["unit_cost"],
        "total": row["production_cost"],
        "paid": None,
        "due": None,
        "notes": row["notes"] or "",
        "lines": lines,
    })
