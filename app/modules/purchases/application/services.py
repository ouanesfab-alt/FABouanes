from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchases.api.schemas import PurchaseFormSchema
from app.modules.purchases.application.queries import PurchaseQueries
from app.modules.purchases.application.commands import PurchaseCommands


class PurchaseService:
    """Asynchronous business service layer for the Purchases module, orchestrating Command-Query Separation (CQRS)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = PurchaseQueries(session)
        self.commands = PurchaseCommands(session)

    # ── [QUERIES] ──

    async def list_purchases(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.queries.list_purchases(search, date_from, date_to, page, page_size)

    async def purchase_form_context(self) -> dict:
        return await self.queries.purchase_form_context()

    async def get_purchase_document_context(self, document_id: int) -> Optional[dict]:
        return await self.queries.get_purchase_document_context(document_id)

    async def get_purchase_edit_context(self, purchase_id: int) -> Optional[dict]:
        return await self.queries.get_purchase_edit_context(purchase_id)

    # ── [COMMANDS] ──

    async def create_purchase_from_form(self, schema: PurchaseFormSchema) -> dict:
        return await self.commands.create_purchase_from_form(schema)

    async def edit_purchase_document_from_form(self, document_id: int, schema: PurchaseFormSchema) -> dict:
        return await self.commands.edit_purchase_document_from_form(document_id, schema)

    async def edit_purchase_from_form(self, purchase_id: int, schema: PurchaseFormSchema) -> dict:
        return await self.commands.edit_purchase_from_form(purchase_id, schema)

    async def delete_purchase_by_id(self, purchase_id: int) -> bool:
        return await self.commands.delete_purchase_by_id(purchase_id)
