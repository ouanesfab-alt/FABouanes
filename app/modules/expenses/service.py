"""Logique métier du module Dépenses — utilise l'Event Bus."""
from __future__ import annotations

from app.core.events import DomainEvent, emit
from app.modules.expenses.repository import (
    EXPENSE_CATEGORIES,
    PAYMENT_METHODS,
    create_expense as _db_create,
    delete_expense as _db_delete,
    get_all_expenses,
    get_expense_by_id,
    update_expense as _db_update,
)


def list_expenses(filters=None) -> list[dict]:
    return get_all_expenses(filters)


def get_expense(expense_id: int) -> dict | None:
    return get_expense_by_id(expense_id)


def add_expense(date: str, category: str, description: str, amount: float, method: str = "cash") -> int:
    expense_id = _db_create(date, category, description, amount, method)
    created = get_expense_by_id(expense_id)
    emit(DomainEvent("create", "expense", expense_id, f"{category}: {description or '-'} ({amount})", after=created))
    return expense_id


def modify_expense(expense_id: int, date: str, category: str, description: str, amount: float, method: str = "cash") -> None:
    before = get_expense_by_id(expense_id)
    _db_update(expense_id, date, category, description, amount, method)
    after = get_expense_by_id(expense_id)
    emit(DomainEvent("update", "expense", expense_id, f"{category}: {description or '-'} ({amount})", before=before, after=after))


def remove_expense(expense_id: int) -> bool:
    before = get_expense_by_id(expense_id)
    if not before:
        return False
    _db_delete(expense_id)
    emit(DomainEvent("delete", "expense", expense_id, f"Suppression dépense #{expense_id}", before=before))
    return True


def get_categories() -> list[tuple[str, str]]:
    return EXPENSE_CATEGORIES


def get_payment_methods() -> list[tuple[str, str]]:
    return PAYMENT_METHODS
