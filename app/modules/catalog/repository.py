from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlmodel import select, func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import RawMaterial, FinishedProduct, SavedRecipe, SavedRecipeItem
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
        result = await self.session.execute(
            text("""
                SELECT 1 FROM purchases WHERE raw_material_id = :mid
                UNION SELECT 1 FROM raw_sales WHERE raw_material_id = :mid
                UNION SELECT 1 FROM production_batch_items WHERE raw_material_id = :mid
                LIMIT 1
            """),
            {"mid": material_id},
        )
        return result.first() is not None

    async def get_30d_velocities(self, cutoff_date_str: str) -> Dict[int, float]:
        """Calculate 30-day consumption velocity for raw materials."""
        result = await self.session.execute(
            text("""
                WITH consumed AS (
                    SELECT raw_material_id, SUM(qty) AS consumed_30d
                    FROM (
                        SELECT raw_material_id,
                               CASE
                                   WHEN lower(unit) LIKE 'sac%' THEN quantity * COALESCE(NULLIF(regexp_replace(unit, '[^0-9.]', '', 'g'), ''), '50')::numeric
                                   WHEN lower(unit) IN ('qt', 'quintal') THEN quantity * 100
                                   ELSE quantity
                               END AS qty
                        FROM raw_sales
                        WHERE sale_date >= :cutoff
                        UNION ALL
                        SELECT pbi.raw_material_id, pbi.quantity AS qty
                        FROM production_batch_items pbi
                        JOIN production_batches pb ON pb.id = pbi.batch_id
                        WHERE pb.production_date >= :cutoff
                    ) source
                    GROUP BY raw_material_id
                )
                SELECT rm.id, COALESCE(c.consumed_30d, 0) AS consumed_30d
                FROM raw_materials rm
                LEFT JOIN consumed c ON c.raw_material_id = rm.id
            """),
            {"cutoff": cutoff_date_str},
        )
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
        result = await self.session.execute(
            text("""
                SELECT 1 FROM sales WHERE finished_product_id = :pid
                UNION SELECT 1 FROM production_batches WHERE finished_product_id = :pid
                LIMIT 1
            """),
            {"pid": product_id},
        )
        return result.first() is not None

    async def get_30d_velocities(self, cutoff_date_str: str) -> Dict[int, float]:
        """Calculate 30-day sales velocity for finished products."""
        result = await self.session.execute(
            text("""
                WITH sold AS (
                    SELECT finished_product_id, SUM(quantity) AS sold_30d
                    FROM sales
                    WHERE sale_date >= :cutoff
                    GROUP BY finished_product_id
                )
                SELECT fp.id, COALESCE(s.sold_30d, 0) AS sold_30d
                FROM finished_products fp
                LEFT JOIN sold s ON s.finished_product_id = fp.id
            """),
            {"cutoff": cutoff_date_str},
        )
        return {row.id: float(row.sold_30d) / 30.0 for row in result.all()}


class SavedRecipeRepository(AsyncRepository[SavedRecipe]):
    """Asynchronous repository for SavedRecipe model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SavedRecipe)

    async def get_all_with_products(self) -> List[Dict[str, Any]]:
        """Fetch all recipes joined with product names."""
        result = await self.session.execute(
            text("""
                SELECT sr.id, sr.finished_product_id, sr.name, COALESCE(sr.notes,'') AS notes,
                       sr.created_at, fp.name AS finished_name
                FROM saved_recipes sr
                JOIN finished_products fp ON fp.id = sr.finished_product_id
                ORDER BY fp.name, sr.name
            """)
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_recipe_items(self) -> List[Dict[str, Any]]:
        """Fetch all recipe items joined with raw material names/stock/units."""
        result = await self.session.execute(
            text("""
                SELECT sri.recipe_id, sri.raw_material_id, sri.quantity, sri.position,
                       rm.name AS material_name, rm.stock_qty, rm.unit
                FROM saved_recipe_items sri
                JOIN raw_materials rm ON rm.id = sri.raw_material_id
                ORDER BY sri.recipe_id, sri.position, sri.id
            """)
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def find_by_product_and_name(self, product_id: int, name: str) -> Optional[SavedRecipe]:
        statement = select(SavedRecipe).where(
            SavedRecipe.finished_product_id == product_id,
            func.lower(SavedRecipe.name) == name.strip().lower()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def delete_recipe_items(self, recipe_id: int) -> None:
        await self.session.execute(
            text("DELETE FROM saved_recipe_items WHERE recipe_id = :rid"),
            {"rid": recipe_id}
        )

    async def add_recipe_item(self, recipe_item: SavedRecipeItem) -> SavedRecipeItem:
        self.session.add(recipe_item)
        return recipe_item
