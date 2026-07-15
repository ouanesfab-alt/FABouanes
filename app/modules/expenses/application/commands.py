from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, emit
from app.core.perf_cache import invalidate_cache_domains
from app.modules.expenses.infrastructure.repository import (
    create_expense as _db_create,
    delete_expense as _db_delete,
    get_expense_by_id,
    update_expense as _db_update,
)
from app.modules.expenses.api.schemas import ExpenseCreateSchema, ExpenseUpdateSchema


class ExpensesCommands:
    """Gestion des commandes (Commands / écritures) du module Dépenses."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_expense(self, schema: ExpenseCreateSchema) -> int:
        expense_id = await _db_create(
            self.session,
            schema.date,
            schema.category,
            schema.description or "",
            schema.amount,
            schema.payment_method
        )
        created = await get_expense_by_id(self.session, expense_id)
        created_dict = created.model_dump() if created else None
        emit(
            DomainEvent(
                "create",
                "expense",
                expense_id,
                f"{schema.category}: {schema.description or '-'} ({schema.amount})",
                after=created_dict
            )
        )
        invalidate_cache_domains("dashboard")
        return expense_id

    async def modify_expense(self, expense_id: int, schema: ExpenseUpdateSchema) -> None:
        before = await get_expense_by_id(self.session, expense_id)
        before_dict = before.model_dump() if before else None

        await _db_update(
            self.session,
            expense_id,
            schema.date,
            schema.category,
            schema.description or "",
            schema.amount,
            schema.payment_method
        )

        after = await get_expense_by_id(self.session, expense_id)
        after_dict = after.model_dump() if after else None
        emit(
            DomainEvent(
                "update",
                "expense",
                expense_id,
                f"{schema.category}: {schema.description or '-'} ({schema.amount})",
                before=before_dict,
                after=after_dict
            )
        )
        invalidate_cache_domains("dashboard")

    async def remove_expense(self, expense_id: int) -> bool:
        before = await get_expense_by_id(self.session, expense_id)
        before_dict = before.model_dump() if before else None
        if not before:
            return False
        await _db_delete(self.session, expense_id)
        emit(
            DomainEvent(
                "delete",
                "expense",
                expense_id,
                f"Suppression dépense #{expense_id}",
                before=before_dict
            )
        )
        invalidate_cache_domains("dashboard")
        return True
