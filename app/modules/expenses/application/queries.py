from __future__ import annotations

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Expense
from app.modules.expenses.infrastructure.repository import (
    get_all_expenses,
    get_expense_by_id,
    EXPENSE_CATEGORIES,
    PAYMENT_METHODS,
)


class ExpensesQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Dépenses."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_expenses(self, filters: dict = None) -> List[Expense]:
        return await get_all_expenses(self.session, filters)

    async def get_expense(self, expense_id: int) -> Optional[Expense]:
        return await get_expense_by_id(self.session, expense_id)

    def get_categories(self) -> List[Tuple[str, str]]:
        return EXPENSE_CATEGORIES

    def get_payment_methods(self) -> List[Tuple[str, str]]:
        return PAYMENT_METHODS
