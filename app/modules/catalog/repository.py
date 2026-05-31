from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlmodel import select, func, case, literal, union_all, cast, Numeric, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    RawMaterial, FinishedProduct, SavedRecipe, SavedRecipeItem,
    Purchase, RawSale, Sale, ProductionBatch, ProductionBatchItem
)
from app.repositories.base_repository import AsyncRepository


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
            .where(RawSale.sale_date >= cutoff_date_str)
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
        sold_q = (
            select(
                Sale.finished_product_id,
                func.sum(Sale.quantity).label("sold_30d")
            )
            .where(Sale.sale_date >= cutoff_date_str)
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
