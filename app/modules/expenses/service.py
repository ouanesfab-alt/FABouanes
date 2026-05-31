"""Logique métier du module Dépenses — utilise l'Event Bus."""
from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.events import DomainEvent, emit
from app.core.perf_cache import invalidate_cache_domains
from app.core.models import Expense
from app.modules.expenses.repository import (
    EXPENSE_CATEGORIES,
    PAYMENT_METHODS,
    create_expense as _db_create,
    delete_expense as _db_delete,
    get_all_expenses,
    get_expense_by_id,
    update_expense as _db_update,
)


async def list_expenses(db: AsyncSession, filters=None) -> list[Expense]:
    return await get_all_expenses(db, filters)


async def get_expense(db: AsyncSession, expense_id: int) -> Expense | None:
    return await get_expense_by_id(db, expense_id)


async def add_expense(db: AsyncSession, date: Any, category: str, description: str, amount: float, method: str = "cash") -> int:
    expense_id = await _db_create(db, date, category, description, amount, method)
    created = await get_expense_by_id(db, expense_id)
    created_dict = created.model_dump() if created else None
    emit(DomainEvent("create", "expense", expense_id, f"{category}: {description or '-'} ({amount})", after=created_dict))
    invalidate_cache_domains("dashboard")
    return expense_id


async def modify_expense(db: AsyncSession, expense_id: int, date: Any, category: str, description: str, amount: float, method: str = "cash") -> None:
    before = await get_expense_by_id(db, expense_id)
    before_dict = before.model_dump() if before else None
    await _db_update(db, expense_id, date, category, description, amount, method)
    after = await get_expense_by_id(db, expense_id)
    after_dict = after.model_dump() if after else None
    emit(DomainEvent("update", "expense", expense_id, f"{category}: {description or '-'} ({amount})", before=before_dict, after=after_dict))
    invalidate_cache_domains("dashboard")


async def remove_expense(db: AsyncSession, expense_id: int) -> bool:
    before = await get_expense_by_id(db, expense_id)
    before_dict = before.model_dump() if before else None
    if not before:
        return False
    await _db_delete(db, expense_id)
    emit(DomainEvent("delete", "expense", expense_id, f"Suppression dépense #{expense_id}", before=before_dict))
    invalidate_cache_domains("dashboard")
    return True


def get_categories() -> list[tuple[str, str]]:
    return EXPENSE_CATEGORIES


def get_payment_methods() -> list[tuple[str, str]]:
    return PAYMENT_METHODS
