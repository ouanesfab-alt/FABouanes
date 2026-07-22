from __future__ import annotations

from collections import defaultdict
from typing import Any
from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker, ensure_transaction
from app.core.helpers import async_compat
from app.core.models import SavedRecipe, SavedRecipeItem, FinishedProduct, RawMaterial


@async_compat
async def load_saved_recipes(db: AsyncSession | None = None) -> list[dict[str, Any]]:
    async with ensure_transaction(db) as session:
        return await _load_saved_recipes_impl(session)


async def _load_saved_recipes_impl(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(
            SavedRecipe.id,
            SavedRecipe.finished_product_id,
            SavedRecipe.name,
            func.coalesce(SavedRecipe.notes, "").label("notes"),
            SavedRecipe.created_at,
            FinishedProduct.name.label("finished_name"),
        )
        .select_from(SavedRecipe)
        .join(FinishedProduct, FinishedProduct.id == SavedRecipe.finished_product_id)
        .order_by(FinishedProduct.name, SavedRecipe.name)
    )
    res = await db.execute(stmt)
    recipes = [dict(row._mapping) for row in res.fetchall()]
    if not recipes:
        return []

    item_stmt = (
        select(
            SavedRecipeItem.recipe_id,
            SavedRecipeItem.raw_material_id,
            SavedRecipeItem.quantity,
            SavedRecipeItem.position,
            RawMaterial.name.label("material_name"),
            RawMaterial.stock_qty,
            RawMaterial.unit,
        )
        .select_from(SavedRecipeItem)
        .join(RawMaterial, RawMaterial.id == SavedRecipeItem.raw_material_id)
        .order_by(SavedRecipeItem.recipe_id, SavedRecipeItem.position, SavedRecipeItem.id)
    )
    item_res = await db.execute(item_stmt)
    item_rows = [dict(row._mapping) for row in item_res.fetchall()]

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


@async_compat
async def save_recipe_definition(
    finished_id: int,
    recipe_name: str,
    notes: str,
    recipe_lines: list[dict[str, Any]],
    user_id: int | None = None,
    db: AsyncSession | None = None,
) -> int | None:
    async with ensure_transaction(db) as session:
        return await _save_recipe_definition_impl(finished_id, recipe_name, notes, recipe_lines, user_id, session)


async def _save_recipe_definition_impl(
    finished_id: int,
    recipe_name: str,
    notes: str,
    recipe_lines: list[dict[str, Any]],
    user_id: int | None,
    db: AsyncSession,
) -> int | None:
    clean_name = (recipe_name or "").strip()
    if not clean_name or not recipe_lines:
        return None
    stmt = select(SavedRecipe).where(
        SavedRecipe.finished_product_id == finished_id,
        func.lower(SavedRecipe.name) == func.lower(clean_name),
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        recipe_id = existing.id
        await db.execute(
            update(SavedRecipe)
            .where(SavedRecipe.id == recipe_id)
            .values(
                notes=notes,
                updated_at=func.current_timestamp(),
                created_by_user_id=func.coalesce(SavedRecipe.created_by_user_id, user_id),
            )
        )
        await db.execute(delete(SavedRecipeItem).where(SavedRecipeItem.recipe_id == recipe_id))
    else:
        new_recipe = SavedRecipe(
            finished_product_id=finished_id,
            name=clean_name,
            notes=notes,
            created_by_user_id=user_id,
        )
        db.add(new_recipe)
        await db.flush()
        recipe_id = new_recipe.id

    for position, line in enumerate(recipe_lines, start=1):
        item = SavedRecipeItem(
            recipe_id=recipe_id,
            raw_material_id=int(line["material"]["id"]),
            quantity=float(line["qty"]),
            position=position,
        )
        db.add(item)
    await db.flush()
    return recipe_id
