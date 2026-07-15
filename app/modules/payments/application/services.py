from __future__ import annotations

from typing import Tuple, Optional, List
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.api.schemas import PaymentFormSchema
from app.modules.payments.application.queries import PaymentsQueries
from app.modules.payments.application.commands import PaymentsCommands


class PaymentsService:
    """Business service layer for the Payments module coordinating Command-Query Separation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = PaymentsQueries(session)
        self.commands = PaymentsCommands(session)

    # ── [QUERIES] ──

    async def get_client_balance(self, client_id: int) -> float:
        return await self.queries.get_client_balance(client_id)

    async def get_open_credit_entries(self, client_id: int | None = None) -> List[dict]:
        return await self.queries.get_open_credit_entries(client_id)

    async def get_edit_payment_context(self, payment_id: int) -> Optional[dict]:
        return await self.queries.get_edit_payment_context(payment_id)

    async def get_payment_form_context(self) -> dict:
        return await self.queries.get_payment_form_context()

    # ── [COMMANDS] ──

    async def create_payment_from_form(self, schema: PaymentFormSchema) -> Tuple[int, str]:
        return await self.commands.create_payment_from_form(schema)

    async def edit_payment_from_form(self, payment_id: int, schema: PaymentFormSchema) -> int:
        return await self.commands.edit_payment_from_form(payment_id, schema)

    async def delete_payment_by_id(self, payment_id: int) -> bool:
        return await self.commands.delete_payment_by_id(payment_id)

    async def create_mobile_payment(
        self,
        client_id: int,
        amount: float,
        payment_date: str | date,
        notes: str,
        recorded_by: int | None = None,
    ) -> dict:
        return await self.commands.create_mobile_payment(
            client_id=client_id,
            amount=amount,
            payment_date=payment_date,
            notes=notes,
            recorded_by=recorded_by
        )
