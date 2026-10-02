# -*- coding: utf-8 -*-
"""Service module for Production domain."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import log_activity
from app.core.async_db import get_async_sessionmaker
from app.core.audit import audit_event
from app.core.helpers import async_compat, to_float
from app.core.models import FinishedProduct, ProductionBatch, ProductionBatchItem, RawMaterial, SavedRecipe
from app.core.perf_cache import async_cached_result
from app.core.request_state import get_state_value
from app.core.storage import backup_database, mark_backup_needed
from app.modules.production.repository import (
    ProductionBatchItemRepository,
    ProductionBatchRepository,
    list_production_page_context,
    production_form_context,
)
from app.modules.sales.repository import invalidate_sellable_items_cache
from app.services.recipe_service import save_recipe_definition
from app.services.stock_service import apply_finished_production, apply_raw_material_consumption, reverse_production


class ProductionService:
    """Asynchronous business service layer for the Production domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.batch_repo = ProductionBatchRepository(session)
        self.item_repo = ProductionBatchItemRepository(session)

    async def get_page_context(self, args: dict | None = None) -> dict:
        return await self.batch_repo.list_page_context(args)

    async def get_form_context(self) -> dict:
        return await self.batch_repo.get_form_context()

    async def create_production(self, form) -> dict:
        return await _create_production_from_form_impl(form, self.session)

    async def delete_production(self, batch_id: int) -> bool:
        return await _delete_production_by_id_impl(batch_id, self.session)

    async def update_notes(self, batch_id: int, production_date: str, notes: str) -> None:
        await _update_production_notes_impl(batch_id, production_date, notes, self.session)


@async_compat
async def productions_context(args=None, db: AsyncSession | None = None):
    args = args or {}
    cache_key = tuple(sorted((str(key), str(value)) for key, value in dict(args).items()))
    return await async_cached_result(
        ("productions_context", cache_key),
        lambda: list_production_page_context(args, db=db),
        ttl_seconds=30.0,
    )


@async_compat
async def new_production_context(db: AsyncSession | None = None):
    return await production_form_context(db=db)


def _current_user_id() -> int | None:
    user = get_state_value("user")
    if user:
        try:
            return int(user["id"])
        except Exception:
            return None
    return None


@async_compat
async def create_production_from_form(form, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await ProductionService(session).create_production(form)
    return await ProductionService(db).create_production(form)


async def _create_production_from_form_impl(form, db: AsyncSession):
    finished_id = int(form["finished_product_id"])
    output_qty = to_float(form.get("output_quantity"))

    production_date_val = form.get("production_date")
    if production_date_val is None:
        production_date_obj = date.today()
    elif isinstance(production_date_val, date):
        production_date_obj = production_date_val
    else:
        production_date_obj = date.fromisoformat(str(production_date_val))

    notes = (form.get("notes") or "").strip()
    recipe_name = (form.get("recipe_name") or "").strip()
    save_recipe_val = form.get("save_recipe")
    save_recipe_flag = (
        str(save_recipe_val if save_recipe_val is not None else "1").strip().lower() not in ("0", "false", "off")
    )

    if hasattr(form, "getlist"):
        raw_ids = form.getlist("raw_material_id[]") or form.getlist("raw_material_ids")
        quantities = form.getlist("quantity[]") or form.getlist("quantities")
    elif isinstance(form, dict):
        if "items" in form and isinstance(form["items"], list):
            raw_ids = [
                item.get("raw_material_id") if isinstance(item, dict) else getattr(item, "raw_material_id", None)
                for item in form["items"]
            ]
            quantities = [
                item.get("quantity") if isinstance(item, dict) else getattr(item, "quantity", 0)
                for item in form["items"]
            ]
        else:
            raw_ids = form.get("raw_material_id[]") or form.get("raw_material_ids") or []
            quantities = form.get("quantity[]") or form.get("quantities") or []
            if not isinstance(raw_ids, list):
                raw_ids = [raw_ids] if raw_ids else []
            if not isinstance(quantities, list):
                quantities = [quantities] if quantities else []
    else:
        raw_ids = []
        quantities = []

    if production_date_obj > date.today():
        raise ValueError("La date de production ne peut pas etre dans le futur.")
    if output_qty <= 0:
        raise ValueError("La quantite produite doit etre superieure a zero.")

    product_res = await db.execute(select(FinishedProduct).where(FinishedProduct.id == finished_id))
    product_obj = product_res.scalar_one_or_none()
    if not product_obj:
        raise ValueError("Produit final introuvable.")
    product = product_obj.model_dump()

    # Filter valid raw IDs and quantities first
    valid_inputs = []
    for raw_id, qty_str in zip(raw_ids, quantities):
        if not raw_id:
            continue
        qty = to_float(qty_str)
        if qty <= 0:
            continue
        valid_inputs.append((int(raw_id), qty))

    recipe_lines = []
    total_cost = 0.0
    total_recipe_qty = 0.0

    if valid_inputs:
        ids_to_query = [x[0] for x in valid_inputs]
        materials_res = await db.execute(select(RawMaterial).where(RawMaterial.id.in_(ids_to_query)))
        materials_rows = [m.model_dump() for m in materials_res.scalars().all()]
        materials_map = {m["id"]: m for m in materials_rows}

        from collections import defaultdict
        needed_by_raw = defaultdict(float)
        for raw_id, qty in valid_inputs:
            needed_by_raw[raw_id] += qty

        for raw_id, total_needed in needed_by_raw.items():
            material = materials_map.get(raw_id)
            if not material:
                raise ValueError("Une matière première selectionnee est introuvable.")
            if total_needed > float(material["stock_qty"]):
                raise ValueError(f"Stock insuffisant pour {material['name']}.")

        for raw_id, qty in valid_inputs:
            material = materials_map.get(raw_id)
            line_cost = qty * float(material["avg_cost"])
            recipe_lines.append(
                {"material": material, "qty": qty, "unit_cost": float(material["avg_cost"]), "line_cost": line_cost}
            )
            total_cost += line_cost
            total_recipe_qty += qty

    if not recipe_lines:
        raise ValueError("Ajoute au moins une matière première dans la recette.")

    recipe_id = None

    batch = ProductionBatch(
        finished_product_id=finished_id,
        output_quantity=output_qty,
        production_cost=total_cost,
        unit_cost=(total_cost / output_qty) if output_qty else 0,
        production_date=production_date_obj,
        notes=notes,
    )
    db.add(batch)
    await db.flush()
    batch_id = batch.id

    for line in recipe_lines:
        item = ProductionBatchItem(
            batch_id=batch_id,
            raw_material_id=int(line["material"]["id"]),
            quantity=line["qty"],
            unit_cost_snapshot=line["unit_cost"],
            line_cost=line["line_cost"],
        )
        db.add(item)
        await apply_raw_material_consumption(
            line["material"], line["qty"], "production", batch_id, "create_production", db=db
        )

    await apply_finished_production(product, output_qty, total_cost, batch_id, db=db)

    if save_recipe_flag:
        recipe_id = await save_recipe_definition(
            finished_id, recipe_name or f"Recette {product['name']}", notes, recipe_lines, _current_user_id(), db=db
        )

    batch_res = await db.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
    batch_obj = batch_res.scalar_one_or_none()
    batch_dict = batch_obj.model_dump() if batch_obj else None

    log_activity(
        "create_production", "production", batch_id, f"produit #{finished_id} sortie={output_qty}kg cout={total_cost}"
    )
    audit_event(
        "create_production",
        "production",
        batch_id,
        after=batch_dict,
        meta={
            "recipe_id": recipe_id,
            "lines": [{"raw_material_id": line["material"]["id"], "quantity": line["qty"]} for line in recipe_lines],
        },
    )
    if recipe_id:
        recipe_res = await db.execute(select(SavedRecipe).where(SavedRecipe.id == recipe_id))
        recipe_obj = recipe_res.scalar_one_or_none()
        recipe_dict = recipe_obj.model_dump() if recipe_obj else None
        audit_event("save_recipe", "recipe", recipe_id, after=recipe_dict)

    invalidate_sellable_items_cache()
    mark_backup_needed("create_production")
    remainder = output_qty - total_recipe_qty
    return {
        "batch_id": batch_id,
        "recipe_id": recipe_id,
        "recipe_label": recipe_name or f"Recette {product['name']}",
        "remainder": remainder,
    }


@async_compat
async def delete_production_by_id(batch_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await ProductionService(session).delete_production(batch_id)
    return await ProductionService(db).delete_production(batch_id)


async def _delete_production_by_id_impl(batch_id: int, db: AsyncSession) -> bool:
    batch_res = await db.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
    batch_obj = batch_res.scalar_one_or_none()
    batch_dict = batch_obj.model_dump() if batch_obj else None

    ok = await reverse_production(batch_id, db=db)
    if ok:
        log_activity("delete_production", "production", batch_id, "Suppression production")
        audit_event("delete_production", "production", batch_id, before=batch_dict, after=None)
        invalidate_sellable_items_cache()
        mark_backup_needed("delete_production")
    return ok


@async_compat
async def update_production_notes(
    batch_id: int,
    production_date: str,
    notes: str,
    db: AsyncSession | None = None,
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _update_production_notes_impl(batch_id, production_date, notes, session)
            await session.commit()
            return
    await _update_production_notes_impl(batch_id, production_date, notes, db)


async def _update_production_notes_impl(
    batch_id: int,
    production_date: str,
    notes: str,
    db: AsyncSession,
) -> None:
    if not batch_id:
        raise ValueError("Identifiant manquant.")

    before_res = await db.execute(
        text("SELECT * FROM production_batches WHERE id = :batch_id"),
        {"batch_id": batch_id},
    )
    before_row = before_res.first()
    if not before_row:
        raise ValueError("Production introuvable.")
    before = dict(before_row._mapping)

    updates = {}
    if production_date:
        updates["production_date"] = production_date
    updates["notes"] = notes

    ALLOWED_KEYS = {"production_date", "notes"}
    for key in updates:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"Key {key} is not allowed for update")

    if not updates:
        return

    sets = ", ".join(f"{key}=:{key}" for key in updates)
    values = {**updates, "batch_id": batch_id}
    await db.execute(text(f"UPDATE production_batches SET {sets} WHERE id = :batch_id"), values)

    after_res = await db.execute(
        text("SELECT * FROM production_batches WHERE id = :batch_id"),
        {"batch_id": batch_id},
    )
    after_row = after_res.first()
    after = dict(after_row._mapping) if after_row else before

    log_activity("edit_production_notes", "production", batch_id, f"date={production_date}")
    audit_event("edit_production_notes", "production", batch_id, before=before, after=after)
    backup_database("edit_production_notes")
