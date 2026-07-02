from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlmodel import select, func, case, literal, union_all, cast, Numeric, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.core.models import (
    RawMaterial, FinishedProduct, SavedRecipe, SavedRecipeItem,
    Purchase, RawSale, Sale, ProductionBatch, ProductionBatchItem,
    StockMovement, Supplier
)
from app.core.base_repository import AsyncRepository
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat, db_task_compat
from app.utils.pagination import pagination_context, parse_pagination
from app.services.recipe_service import load_saved_recipes


class RawMaterialRepository(AsyncRepository[RawMaterial]):
    """Asynchronous repository for RawMaterial model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RawMaterial)

    async def get_by_id(self, material_id: int) -> Optional[RawMaterial]:
        return await self.get(material_id)

    async def get_all_ordered(self) -> List[RawMaterial]:
        statement = select(RawMaterial).order_by(RawMaterial.name)
        results = await self.session.execute(statement)
        return list(results.scalars().all())

    async def is_linked(self, material_id: int) -> bool:
        """Check if raw material is linked to purchases, raw sales, or production batch items."""
        stmt1 = select(literal(1)).where(Purchase.raw_material_id == material_id)
        stmt2 = select(literal(1)).where(RawSale.raw_material_id == material_id)
        stmt3 = select(literal(1)).where(ProductionBatchItem.raw_material_id == material_id)
        union_stmt = union_all(stmt1, stmt2, stmt3).limit(1)
        result = await self.session.execute(union_stmt)
        return result.first() is not None

    async def get_30d_velocities(self, cutoff_date_str: str) -> Dict[int, float]:
        """Calculate 30-day consumption velocity for raw materials."""
        from datetime import date
        cutoff_date = date.fromisoformat(cutoff_date_str) if isinstance(cutoff_date_str, str) else cutoff_date_str
        sac_capacity_num = cast(func.coalesce(func.nullif(func.regexp_replace(RawSale.unit, '[^0-9.]', '', 'g'), ''), '50'), Numeric)
        qty_expr = case(
            (func.lower(RawSale.unit).like('sac%'), RawSale.quantity * sac_capacity_num),
            (func.lower(RawSale.unit).in_(['qt', 'quintal']), RawSale.quantity * 100),
            else_=RawSale.quantity
        )
        
        stmt_sales = (
            select(
                RawSale.raw_material_id,
                qty_expr.label("qty")
            )
            .where(RawSale.sale_date >= cutoff_date)
        )
        
        stmt_prod = (
            select(
                ProductionBatchItem.raw_material_id,
                ProductionBatchItem.quantity.label("qty")
            )
            .select_from(ProductionBatchItem)
            .join(ProductionBatch, ProductionBatch.id == ProductionBatchItem.batch_id)
            .where(ProductionBatch.production_date >= cutoff_date_str)
        )
        
        source_q = union_all(stmt_sales, stmt_prod).subquery("source")
        
        consumed_q = (
            select(
                source_q.c.raw_material_id,
                func.sum(source_q.c.qty).label("consumed_30d")
            )
            .group_by(source_q.c.raw_material_id)
        ).subquery("c")
        
        stmt = (
            select(
                RawMaterial.id,
                func.coalesce(consumed_q.c.consumed_30d, 0).label("consumed_30d")
            )
            .select_from(RawMaterial)
            .join(consumed_q, consumed_q.c.raw_material_id == RawMaterial.id, isouter=True)
        )
        
        result = await self.session.execute(stmt)
        return {row.id: float(row.consumed_30d) / 30.0 for row in result.all()}


class FinishedProductRepository(AsyncRepository[FinishedProduct]):
    """Asynchronous repository for FinishedProduct model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, FinishedProduct)

    async def get_by_id(self, product_id: int) -> Optional[FinishedProduct]:
        return await self.get(product_id)

    async def get_all_ordered(self) -> List[FinishedProduct]:
        statement = select(FinishedProduct).order_by(FinishedProduct.name)
        results = await self.session.execute(statement)
        return list(results.scalars().all())

    async def is_linked(self, product_id: int) -> bool:
        """Check if finished product is linked to sales or production batches."""
        stmt1 = select(literal(1)).where(Sale.finished_product_id == product_id)
        stmt2 = select(literal(1)).where(ProductionBatch.finished_product_id == product_id)
        union_stmt = union_all(stmt1, stmt2).limit(1)
        result = await self.session.execute(union_stmt)
        return result.first() is not None

    async def get_30d_velocities(self, cutoff_date_str: str) -> Dict[int, float]:
        """Calculate 30-day sales velocity for finished products."""
        from datetime import date
        cutoff_date = date.fromisoformat(cutoff_date_str) if isinstance(cutoff_date_str, str) else cutoff_date_str
        sold_q = (
            select(
                Sale.finished_product_id,
                func.sum(Sale.quantity).label("sold_30d")
            )
            .where(Sale.sale_date >= cutoff_date)
            .group_by(Sale.finished_product_id)
        ).subquery("s")
        
        stmt = (
            select(
                FinishedProduct.id,
                func.coalesce(sold_q.c.sold_30d, 0).label("sold_30d")
            )
            .select_from(FinishedProduct)
            .join(sold_q, sold_q.c.finished_product_id == FinishedProduct.id, isouter=True)
        )
        result = await self.session.execute(stmt)
        return {row.id: float(row.sold_30d) / 30.0 for row in result.all()}


class SavedRecipeRepository(AsyncRepository[SavedRecipe]):
    """Asynchronous repository for SavedRecipe model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SavedRecipe)

    async def get_all_with_products(self) -> List[Dict[str, Any]]:
        """Fetch all recipes joined with product names."""
        stmt = (
            select(
                SavedRecipe.id,
                SavedRecipe.finished_product_id,
                SavedRecipe.name,
                func.coalesce(SavedRecipe.notes, '').label("notes"),
                SavedRecipe.created_at,
                FinishedProduct.name.label("finished_name")
            )
            .select_from(SavedRecipe)
            .join(FinishedProduct, FinishedProduct.id == SavedRecipe.finished_product_id)
            .order_by(FinishedProduct.name, SavedRecipe.name)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_recipe_items(self) -> List[Dict[str, Any]]:
        """Fetch all recipe items joined with raw material names/stock/units."""
        stmt = (
            select(
                SavedRecipeItem.recipe_id,
                SavedRecipeItem.raw_material_id,
                SavedRecipeItem.quantity,
                SavedRecipeItem.position,
                RawMaterial.name.label("material_name"),
                RawMaterial.stock_qty,
                RawMaterial.unit
            )
            .select_from(SavedRecipeItem)
            .join(RawMaterial, RawMaterial.id == SavedRecipeItem.raw_material_id)
            .order_by(SavedRecipeItem.recipe_id, SavedRecipeItem.position, SavedRecipeItem.id)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]

    async def find_by_product_and_name(self, product_id: int, name: str) -> Optional[SavedRecipe]:
        statement = select(SavedRecipe).where(
            SavedRecipe.finished_product_id == product_id,
            func.lower(SavedRecipe.name) == name.strip().lower()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def delete_recipe_items(self, recipe_id: int) -> None:
        stmt = delete(SavedRecipeItem).where(SavedRecipeItem.recipe_id == recipe_id)
        await self.session.execute(stmt)

    async def add_recipe_item(self, recipe_item: SavedRecipeItem) -> SavedRecipeItem:
        self.session.add(recipe_item)
        return recipe_item


# --- Stock Movement and List Queries (migrated from stock_repository) ---

@async_compat
async def insert_stock_movement(
    item_kind: str,
    item_id: int,
    direction: str,
    quantity: float,
    unit: str,
    stock_before: float,
    stock_after: float,
    reason: str,
    reference_type: str,
    reference_id: int | None,
    username: str,
    db: AsyncSession | None = None,
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _insert_stock_movement_impl(
                item_kind, item_id, direction, quantity, unit,
                stock_before, stock_after, reason, reference_type,
                reference_id, username, session
            )
            await session.commit()
    else:
        await _insert_stock_movement_impl(
            item_kind, item_id, direction, quantity, unit,
            stock_before, stock_after, reason, reference_type,
            reference_id, username, db
        )

async def _insert_stock_movement_impl(
    item_kind: str,
    item_id: int,
    direction: str,
    quantity: float,
    unit: str,
    stock_before: float,
    stock_after: float,
    reason: str,
    reference_type: str,
    reference_id: int | None,
    username: str,
    db: AsyncSession,
) -> None:
    movement = StockMovement(
        item_kind=item_kind,
        item_id=int(item_id),
        direction=direction,
        quantity=Decimal(str(quantity)),
        unit=unit,
        stock_before=Decimal(str(stock_before)),
        stock_after=Decimal(str(stock_after)),
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by_username=username,
    )
    db.add(movement)


async def list_raw_materials(
    search: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as sess:
            return await _list_raw_materials_impl(search, status, page, page_size, sess)
    return await _list_raw_materials_impl(search, status, page, page_size, db)

async def _list_raw_materials_impl(
    search: str | None,
    status: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    stmt = select(
        *RawMaterial.__table__.columns,
        case(
            (RawMaterial.stock_qty <= func.coalesce(func.nullif(RawMaterial.threshold_qty, 0), RawMaterial.alert_threshold), 1),
            else_=0
        ).label("is_low_stock"),
        literal("'raw'").label("item_type")
    )
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                RawMaterial.name.ilike(search_filter),
                RawMaterial.unit.ilike(search_filter)
            )
        )
    if status == "low":
        stmt = stmt.where(
            RawMaterial.stock_qty <= func.coalesce(func.nullif(RawMaterial.threshold_qty, 0), RawMaterial.alert_threshold)
        )
        
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0
    
    stmt = stmt.order_by(RawMaterial.name).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    rows = [dict(r._mapping) for r in res.fetchall()]
    return rows, total


async def list_finished_products(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as sess:
            return await _list_finished_products_impl(search, page, page_size, sess)
    return await _list_finished_products_impl(search, page, page_size, db)

async def _list_finished_products_impl(
    search: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    stmt = select(
        *FinishedProduct.__table__.columns,
        literal("'finished'").label("item_type")
    )
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                FinishedProduct.name.ilike(search_filter),
                FinishedProduct.default_unit.ilike(search_filter)
            )
        )
        
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0
    
    stmt = stmt.order_by(FinishedProduct.name).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    rows = [dict(r._mapping) for r in res.fetchall()]
    return rows, total


# --- Production Queries (migrated from production_repository) ---

@db_task_compat
async def list_production_page_context(args=None, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_production_page_context_impl(args, session)
    return await _list_production_page_context_impl(args, db)


async def _list_production_page_context_impl(args, db: AsyncSession):
    from datetime import date
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


@async_compat
async def list_production_batches(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_production_batches_impl(search, date_from, date_to, page, page_size, session)
    return await _list_production_batches_impl(search, date_from, date_to, page, page_size, db)


async def _list_production_batches_impl(
    search: str | None,
    date_from: str | None,
    date_to: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    from datetime import date
    date_from_obj = date.fromisoformat(date_from) if date_from else None
    date_to_obj = date.fromisoformat(date_to) if date_to else None
    stmt = select(
        ProductionBatch,
        FinishedProduct.name.label("product_name"),
        FinishedProduct.default_unit.label("product_unit")
    ).join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id)
    
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                FinishedProduct.name.ilike(search_pattern),
                func.coalesce(ProductionBatch.notes, '').ilike(search_pattern)
            )
        )
    if date_from_obj:
        stmt = stmt.where(ProductionBatch.production_date >= date_from_obj)
    if date_to_obj:
        stmt = stmt.where(ProductionBatch.production_date <= date_to_obj)
        
    stmt = stmt.add_columns(func.count().over().label("_total_count"))
    stmt = stmt.order_by(ProductionBatch.production_date.desc(), ProductionBatch.id.desc()).offset((page - 1) * page_size).limit(page_size)
    
    res = await db.execute(stmt)
    rows = []
    for row in res.all():
        dct = row[0].model_dump()
        dct["product_name"] = row.product_name
        dct["product_unit"] = row.product_unit
        dct["_total_count"] = row._total_count
        rows.append(dct)
        
    total = int(rows[0]["_total_count"]) if rows else 0
    return rows, total


@async_compat
async def list_recipes(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_recipes_impl(page, page_size, session)
    return await _list_recipes_impl(page, page_size, db)


async def _list_recipes_impl(
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    stmt = select(
        SavedRecipe,
        FinishedProduct.name.label("finished_product_name")
    ).join(FinishedProduct, FinishedProduct.id == SavedRecipe.finished_product_id)
    
    stmt = stmt.add_columns(func.count().over().label("_total_count"))
    stmt = stmt.order_by(SavedRecipe.id.desc()).offset((page - 1) * page_size).limit(page_size)
    
    res = await db.execute(stmt)
    rows = []
    for row in res.all():
        dct = row[0].model_dump()
        dct["finished_product_name"] = row.finished_product_name
        dct["_total_count"] = row._total_count
        rows.append(dct)
        
    total = int(rows[0]["_total_count"]) if rows else 0
    return rows, total


# --- Supplier Queries (migrated from supplier_repository) ---

async def list_suppliers(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_suppliers_impl(search, page, page_size, session)
    return await _list_suppliers_impl(search, page, page_size, db)

async def _list_suppliers_impl(
    search: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    stmt = select(Supplier)
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                Supplier.name.ilike(search_filter),
                Supplier.phone.ilike(search_filter),
                Supplier.address.ilike(search_filter),
            )
        )
    # Count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginated query ordered by name
    stmt = stmt.order_by(Supplier.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    suppliers = [s.model_dump() for s in result.scalars().all()]
    return suppliers, total

