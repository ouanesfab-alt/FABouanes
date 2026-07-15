from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import RawMaterial, FinishedProduct
from app.modules.catalog.api.schemas import (
    RawMaterialCreateSchema,
    RawMaterialUpdateSchema,
    FinishedProductCreateSchema,
    FinishedProductUpdateSchema,
)
from app.modules.catalog.application.queries import (
    CatalogQueries,
    new_catalog_context,
    raw_material_edit_context,
    product_edit_context,
    quick_add_context,
    resolve_name_from_form,
)
from app.modules.catalog.application.commands import CatalogCommands


class CatalogService:
    """Asynchronous business service layer for the Catalog module, orchestrating Command-Query Separation (CQRS)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = CatalogQueries(session)
        self.commands = CatalogCommands(session)

    # ── [QUERIES] ──

    async def get_raw_material(self, material_id: int) -> Optional[RawMaterial]:
        return await self.queries.get_raw_material(material_id)

    async def get_product(self, product_id: int) -> Optional[FinishedProduct]:
        return await self.queries.get_product(product_id)

    async def catalog_context(self, args: dict = None, path: str = "/catalog") -> dict:
        return await self.queries.catalog_context(args, path)

    async def load_saved_recipes(self) -> List[Dict[str, Any]]:
        return await self.queries.load_saved_recipes()

    def quick_add_context(self, default_target: str = "client") -> dict:
        return quick_add_context(default_target)

    def new_catalog_context(self, kind: str = "raw") -> dict:
        return new_catalog_context(kind)

    def resolve_name_from_form(self, form: dict | Any, kind: str = None) -> str:
        return resolve_name_from_form(form, kind)

    def raw_material_edit_context(self, material: RawMaterial) -> dict:
        return raw_material_edit_context(material)

    def product_edit_context(self, product: FinishedProduct) -> dict:
        return product_edit_context(product)

    # ── [COMMANDS] ──

    async def create_raw_material(self, schema: RawMaterialCreateSchema) -> RawMaterial:
        return await self.commands.create_raw_material(schema)

    async def create_finished_product(self, schema: FinishedProductCreateSchema) -> FinishedProduct:
        return await self.commands.create_finished_product(schema)

    async def update_raw_material(self, material_id: int, schema: RawMaterialUpdateSchema) -> Optional[RawMaterial]:
        return await self.commands.update_raw_material(material_id, schema)

    async def update_finished_product(self, product_id: int, schema: FinishedProductUpdateSchema) -> Optional[FinishedProduct]:
        return await self.commands.update_finished_product(product_id, schema)

    async def delete_raw_material(self, material_id: int) -> bool:
        return await self.commands.delete_raw_material(material_id)

    async def delete_finished_product(self, product_id: int) -> bool:
        return await self.commands.delete_finished_product(product_id)

    async def save_recipe_definition(
        self,
        finished_product_id: int,
        name: str,
        notes: str,
        items: List[Dict[str, Any]],
        user_id: int | None = None,
    ) -> Optional[int]:
        return await self.commands.save_recipe_definition(
            finished_product_id=finished_product_id,
            name=name,
            notes=notes,
            items=items,
            user_id=user_id
        )
