from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import RawMaterial, FinishedProduct, SavedRecipe, SavedRecipeItem
from app.core.events import DomainEvent, emit
from app.core.perf_cache import invalidate_cache_domains
from app.core.helpers import refresh_sale_profits_for_item
from app.modules.catalog.infrastructure.repository import RawMaterialRepository, FinishedProductRepository, SavedRecipeRepository
from app.modules.catalog.api.schemas import (
    RawMaterialCreateSchema,
    RawMaterialUpdateSchema,
    FinishedProductCreateSchema,
    FinishedProductUpdateSchema,
)


class CatalogCommands:
    """Gestion des commandes (Commands / écritures) du module Catalogue."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.raw_repo = RawMaterialRepository(session)
        self.finished_repo = FinishedProductRepository(session)
        self.recipe_repo = SavedRecipeRepository(session)

    async def create_raw_material(self, schema: RawMaterialCreateSchema) -> RawMaterial:
        rm = RawMaterial(
            name=schema.name,
            unit=schema.unit,
            stock_qty=schema.stock_qty,
            avg_cost=schema.avg_cost,
            sale_price=schema.sale_price,
            alert_threshold=schema.alert_threshold,
            threshold_qty=schema.alert_threshold,
        )
        created = await self.raw_repo.create(rm)
        invalidate_cache_domains("catalog")

        emit(
            DomainEvent(
                "create",
                "raw_material",
                created.id,
                created.name,
                after=created.model_dump(),
            )
        )
        return created

    async def create_finished_product(self, schema: FinishedProductCreateSchema) -> FinishedProduct:
        fp = FinishedProduct(
            name=schema.name,
            default_unit=schema.default_unit,
            stock_qty=schema.stock_qty,
            sale_price=schema.sale_price,
            avg_cost=schema.avg_cost,
        )
        created = await self.finished_repo.create(fp)
        invalidate_cache_domains("catalog")

        emit(
            DomainEvent(
                "create",
                "finished_product",
                created.id,
                created.name,
                after=created.model_dump(),
            )
        )
        return created

    async def update_raw_material(self, material_id: int, schema: RawMaterialUpdateSchema) -> Optional[RawMaterial]:
        rm = await self.raw_repo.get_by_id(material_id)
        if not rm:
            return None

        before_dump = rm.model_dump()
        rm.name = schema.name
        rm.unit = schema.unit
        rm.stock_qty = schema.stock_qty
        rm.avg_cost = schema.avg_cost
        rm.sale_price = schema.sale_price
        rm.alert_threshold = schema.alert_threshold
        rm.threshold_qty = schema.alert_threshold

        updated = await self.raw_repo.update(rm)
        invalidate_cache_domains("catalog")

        await asyncio.to_thread(
            refresh_sale_profits_for_item,
            "raw",
            material_id,
            schema.avg_cost,
            schema.sale_price
        )

        emit(
            DomainEvent(
                "update",
                "raw_material",
                material_id,
                f"{updated.name} | achat={updated.avg_cost} | vente={updated.sale_price}",
                before=before_dump,
                after=updated.model_dump(),
            )
        )
        return updated

    async def update_finished_product(self, product_id: int, schema: FinishedProductUpdateSchema) -> Optional[FinishedProduct]:
        fp = await self.finished_repo.get_by_id(product_id)
        if not fp:
            return None

        before_dump = fp.model_dump()
        fp.name = schema.name
        fp.default_unit = schema.default_unit
        fp.stock_qty = schema.stock_qty
        fp.sale_price = schema.sale_price
        fp.avg_cost = schema.avg_cost

        updated = await self.finished_repo.update(fp)
        invalidate_cache_domains("catalog")

        await asyncio.to_thread(
            refresh_sale_profits_for_item,
            "finished",
            product_id,
            schema.avg_cost,
            schema.sale_price
        )

        emit(
            DomainEvent(
                "update",
                "finished_product",
                product_id,
                f"{updated.name} | revient={updated.avg_cost} | vente={updated.sale_price}",
                before=before_dump,
                after=updated.model_dump(),
            )
        )
        return updated

    async def delete_raw_material(self, material_id: int) -> bool:
        rm = await self.raw_repo.get_by_id(material_id)
        if not rm:
            return False

        if await self.raw_repo.is_linked(material_id):
            return False

        before_dump = rm.model_dump()
        success = await self.raw_repo.delete(material_id)

        if success:
            invalidate_cache_domains("catalog")
            emit(
                DomainEvent(
                    "delete",
                    "raw_material",
                    material_id,
                    "Suppression matière",
                    before=before_dump,
                )
            )
        return success

    async def delete_finished_product(self, product_id: int) -> bool:
        fp = await self.finished_repo.get_by_id(product_id)
        if not fp:
            return False

        if await self.finished_repo.is_linked(product_id):
            return False

        before_dump = fp.model_dump()
        success = await self.finished_repo.delete(product_id)

        if success:
            invalidate_cache_domains("catalog")
            emit(
                DomainEvent(
                    "delete",
                    "finished_product",
                    product_id,
                    "Suppression produit",
                    before=before_dump,
                )
            )
        return success

    async def save_recipe_definition(
        self,
        finished_product_id: int,
        name: str,
        notes: str,
        items: List[Dict[str, Any]],
        user_id: int | None = None,
    ) -> Optional[int]:
        clean_name = (name or "").strip()
        if not clean_name or not items:
            return None

        existing = await self.recipe_repo.find_by_product_and_name(finished_product_id, clean_name)
        if existing:
            recipe_id = existing.id
            existing.notes = notes
            existing.created_by_user_id = existing.created_by_user_id or user_id
            await self.recipe_repo.update(existing)
            await self.recipe_repo.delete_recipe_items(recipe_id)
        else:
            recipe = SavedRecipe(
                finished_product_id=finished_product_id,
                name=clean_name,
                notes=notes,
                created_by_user_id=user_id,
            )
            created = await self.recipe_repo.create(recipe)
            recipe_id = created.id

        for pos, item_data in enumerate(items, start=1):
            recipe_item = SavedRecipeItem(
                recipe_id=recipe_id,
                raw_material_id=int(item_data["raw_material_id"]),
                quantity=float(item_data["quantity"]),
                position=pos,
            )
            await self.recipe_repo.add_recipe_item(recipe_item)

        await self.session.commit()
        return recipe_id
