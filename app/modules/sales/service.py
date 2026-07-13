from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sales.schemas_validation import SaleFormSchema
from app.modules.sales.queries import SalesQueries
from app.modules.sales.commands import SalesCommands


class SalesService:
    """Asynchronous business service layer for the Sales module, orchestrating Command-Query Separation (CQRS)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = SalesQueries(session)
        self.commands = SalesCommands(session)

    # ── [QUERIES] ──

    async def list_sales(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.queries.list_sales(
            search=search,
            date_from=date_from,
            date_to=date_to,
            kind=kind,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def sale_form_context(self) -> dict:
        return await self.queries.sale_form_context()

    async def get_sale_document_context(self, document_id: int) -> Optional[dict]:
        return await self.queries.get_sale_document_context(document_id)

    async def get_sale_edit_context(self, kind: str, row_id: int) -> Optional[dict]:
        return await self.queries.get_sale_edit_context(kind, row_id)

    # ── [COMMANDS] ──

    async def create_sale_record(
        self,
        client_id: int | None,
        item_kind: str,
        item_id: int,
        qty: float,
        unit: str,
        unit_price: float,
        sale_type: str,
        sale_date: Any,
        notes: str,
        amount_paid_input: float = 0.0,
        document_id: int | None = None,
        custom_item_name: str = "",
    ) -> Tuple[str, int]:
        return await self.commands.create_sale_record(
            client_id=client_id,
            item_kind=item_kind,
            item_id=item_id,
            qty=qty,
            unit=unit,
            unit_price=unit_price,
            sale_type=sale_type,
            sale_date=sale_date,
            notes=notes,
            amount_paid_input=amount_paid_input,
            document_id=document_id,
            custom_item_name=custom_item_name,
        )

    async def reverse_sale(self, kind: str, row_id: int, recalc: bool = True) -> bool:
        return await self.commands.reverse_sale(kind, row_id, recalc)

    async def record_stock_movement(
        self,
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
    ) -> None:
        return await self.commands.record_stock_movement(
            item_kind=item_kind,
            item_id=item_id,
            direction=direction,
            quantity=quantity,
            unit=unit,
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )

    async def recalc_sale_document_totals(self, document_id: int | None) -> None:
        return await self.commands.recalc_sale_document_totals(document_id)

    async def create_sale_from_form(self, schema: SaleFormSchema) -> dict:
        return await self.commands.create_sale_from_form(schema)

    async def edit_sale_document_from_form(self, document_id: int, schema: SaleFormSchema) -> dict:
        return await self.commands.edit_sale_document_from_form(document_id, schema)

    async def edit_single_sale_from_form(self, kind: str, row_id: int, schema: SaleFormSchema) -> dict:
        return await self.commands.edit_single_sale_from_form(kind, row_id, schema)

    async def delete_sale_by_id(self, kind: str, row_id: int) -> bool:
        return await self.commands.delete_sale_by_id(kind, row_id)
