from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.production.application.queries import ProductionQueries
from app.modules.production.application.commands import ProductionCommands


class ProductionService:
    """Business service layer for the Production module, orchestrating Command-Query Separation (CQRS)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = ProductionQueries(session)
        self.commands = ProductionCommands(session)

    # ── [QUERIES] ──

    async def productions_context(self, args: dict = None) -> dict:
        return await self.queries.productions_context(args)

    async def new_production_context(self) -> dict:
        return await self.queries.new_production_context()

    # ── [COMMANDS] ──

    async def create_production_from_form(self, form: Any) -> dict:
        return await self.commands.create_production_from_form(form)

    async def delete_production_by_id(self, batch_id: int) -> bool:
        return await self.commands.delete_production_by_id(batch_id)
