from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.db_access import execute_db, query_db


def load_saved_recipes() -> list[dict[str, Any]]:
    recipes = [
        dict(row)
        for row in query_db(
            """
            SELECT sr.id, sr.finished_product_id, sr.name, COALESCE(sr.notes,'') AS notes,
                   sr.created_at, fp.name AS finished_name
            FROM saved_recipes sr
            JOIN finished_products fp ON fp.id = sr.finished_product_id
            ORDER BY fp.name, sr.name
            """
        )
    ]
    if not recipes:
        return []
    item_rows = query_db(
        """
        SELECT sri.recipe_id, sri.raw_material_id, sri.quantity, sri.position,
               rm.name AS material_name, rm.stock_qty, rm.unit
        FROM saved_recipe_items sri
        JOIN raw_materials rm ON rm.id = sri.raw_material_id
        ORDER BY sri.recipe_id, sri.position, sri.id
        """
    )
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in item_rows:
        grouped[int(row["recipe_id"])].append(
            {
                "raw_material_id": int(row["raw_material_id"]),
                "quantity": float(row["quantity"]),
                "material_name": row["material_name"],
                "stock_qty": float(row["stock_qty"]),
                "unit": row["unit"],
            }
        )
    for recipe in recipes:
        recipe["items"] = grouped.get(int(recipe["id"]), [])
    return recipes


def save_recipe_definition(
    finished_id: int,
    recipe_name: str,
    notes: str,
    recipe_lines: list[dict[str, Any]],
    user_id: int | None = None,
) -> int | None:
    clean_name = (recipe_name or "").strip()
    if not clean_name or not recipe_lines:
        return None
    existing = query_db(
        "SELECT id FROM saved_recipes WHERE finished_product_id = %s AND lower(name) = lower(?)",
        (finished_id, clean_name),
        one=True,
    )
    if existing:
        recipe_id = int(existing["id"])
        execute_db(
            "UPDATE saved_recipes SET notes = %s, updated_at = CURRENT_TIMESTAMP, created_by_user_id = COALESCE(created_by_user_id, ?) WHERE id = %s",
            (notes, user_id, recipe_id),
        )
        execute_db("DELETE FROM saved_recipe_items WHERE recipe_id = %s", (recipe_id,))
    else:
        recipe_id = execute_db(
            "INSERT INTO saved_recipes (finished_product_id, name, notes, created_by_user_id) VALUES (%s, %s, %s, %s)",
            (finished_id, clean_name, notes, user_id),
        )
    for position, line in enumerate(recipe_lines, start=1):
        execute_db(
            "INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity, position) VALUES (%s, %s, %s, %s)",
            (recipe_id, int(line["material"]["id"]), float(line["qty"]), position),
        )
    return recipe_id
