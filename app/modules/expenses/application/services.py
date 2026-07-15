from __future__ import annotations

from typing import List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Expense
from app.modules.expenses.api.schemas import ExpenseCreateSchema, ExpenseUpdateSchema
from app.modules.expenses.application.queries import ExpensesQueries
from app.modules.expenses.application.commands import ExpensesCommands


class ExpensesService:
    """Business service layer for the Expenses module coordinating Command-Query Separation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = ExpensesQueries(session)
        self.commands = ExpensesCommands(session)

    # ── [QUERIES] ──

    async def list_expenses(self, filters: dict = None) -> List[Expense]:
        return await self.queries.list_expenses(filters)

    async def get_expense(self, expense_id: int) -> Optional[Expense]:
        return await self.queries.get_expense(expense_id)

    def get_categories(self) -> List[Tuple[str, str]]:
        return self.queries.get_categories()

    def get_payment_methods(self) -> List[Tuple[str, str]]:
        return self.queries.get_payment_methods()

    # ── [COMMANDS] ──

    async def add_expense(self, schema: ExpenseCreateSchema) -> int:
        return await self.commands.add_expense(schema)

    async def modify_expense(self, expense_id: int, schema: ExpenseUpdateSchema) -> None:
        await self.commands.modify_expense(expense_id, schema)

    async def remove_expense(self, expense_id: int) -> bool:
        return await self.commands.remove_expense(expense_id)
