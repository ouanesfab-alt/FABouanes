# -*- coding: utf-8 -*-
"""Repository module for Production domain."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat, db_task_compat
from app.core.models import (
    FinishedProduct,
    ProductionBatch,
    ProductionBatchItem,
    RawMaterial,
)
from app.utils.pagination import pagination_context, parse_pagination


@db_task_compat
async def list_production_page_context(args=None, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_production_page_context_impl(args, session)
    return await _list_production_page_context_impl(args, db)


async def _list_production_page_context_impl(args, db: AsyncSession):
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    q = str(args.get("q", "") or "").strip()
    production_date = str(args.get("date", "") or "").strip()
    production_date_obj = date.fromisoformat(production_date) if production_date else None

    stmt = select(
        ProductionBatch,
        FinishedProduct.name.label("finished_name")
    ).join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id)

    if q:
        stmt = stmt.where(func.lower(func.concat(FinishedProduct.name, ' ', func.coalesce(ProductionBatch.notes, ''))).like(f"%{q.lower()}%"))
    if production_date_obj:
        stmt = stmt.where(ProductionBatch.production_date == production_date_obj)

    stmt = stmt.order_by(ProductionBatch.id.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one_or_none() or 0

    stmt = stmt.offset(offset).limit(page_size)
    batches_res = await db.execute(stmt)
    batches_rows = batches_res.all()
    batches = []
    batch_ids = []
    for row in batches_rows:
        dct = row[0].model_dump()
        dct["finished_name"] = row.finished_name
        batches.append(dct)
        batch_ids.append(dct["id"])

    recipe_by_batch: dict[int, list[str]] = {batch_id: [] for batch_id in batch_ids}
    if batch_ids:
        items_stmt = select(
            ProductionBatchItem.batch_id,
            ProductionBatchItem.quantity,
            RawMaterial.name,
            RawMaterial.unit
        ).join(RawMaterial, RawMaterial.id == ProductionBatchItem.raw_material_id).where(ProductionBatchItem.batch_id.in_(batch_ids)).order_by(ProductionBatchItem.batch_id, ProductionBatchItem.id)

        items_res = await db.execute(items_stmt)
        for item in items_res.all():
            recipe_by_batch.setdefault(int(item.batch_id), []).append(
                f"{item.name} {item.quantity} {item.unit}"
            )

    production_rows = []
    for batch in batches:
        row = dict(batch)
        row["recipe_text"] = " + ".join(recipe_by_batch.get(int(batch["id"]), []))
        production_rows.append(row)

    return {
        'productions': production_rows,
        'filters': {'q': q, 'date': production_date},
        'pagination': pagination_context('production', args, total=total, page=page, page_size=page_size),
    }


@async_compat
async def production_form_context(db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _production_form_context_impl(session)
    return await _production_form_context_impl(db)


async def _production_form_context_impl(db: AsyncSession):
    from app.modules.catalog.repository import load_saved_recipes
    raw_res = await db.execute(select(RawMaterial).order_by(RawMaterial.name))
    raw_materials = [r.model_dump() for r in raw_res.scalars().all()]

    prod_res = await db.execute(select(FinishedProduct).order_by(FinishedProduct.name))
    products = [p.model_dump() for p in prod_res.scalars().all()]

    recipes = await load_saved_recipes(db=db)
    return {
        'raw_materials': raw_materials,
        'raw_materials_json': raw_materials,
        'products': products,
        'recipes': recipes,
    }
