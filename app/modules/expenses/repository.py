"""Requêtes SQL du module Dépenses & Charges, implémentées avec SQLAlchemy ORM et AsyncSession."""
from __future__ import annotations

from datetime import datetime, date as d_cls
from typing import Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import AsyncRepository
from app.core.models import Expense

# ── Catégories ──

EXPENSE_CATEGORIES = [
    ("general", "Général"),
    ("transport", "Transport"),
    ("fournitures", "Fournitures"),
    ("loyer", "Loyer / Local"),
    ("salaires", "Salaires"),
    ("maintenance", "Maintenance"),
    ("telecom", "Télécom / Internet"),
    ("energie", "Énergie / Eau"),
    ("impots", "Impôts / Taxes"),
    ("autre", "Autre"),
]

PAYMENT_METHODS = [
    ("cash", "Espèces"),
    ("cheque", "Chèque"),
    ("virement", "Virement"),
    ("autre", "Autre"),
]


class ExpenseRepository(AsyncRepository[Expense]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Expense)


# ── CRUD ──

async def get_all_expenses(db: AsyncSession, filters: dict[str, Any] | None = None) -> list[Expense]:
    stmt = select(Expense)
    conditions = []
    if filters:
        if filters.get("category"):
            conditions.append(Expense.category == filters["category"])
        if filters.get("date_from") and str(filters["date_from"]).strip():
            conditions.append(Expense.date >= filters["date_from"])
        if filters.get("date_to") and str(filters["date_to"]).strip():
            conditions.append(Expense.date <= filters["date_to"])
        if filters.get("q") and str(filters["q"]).strip():
            needle = f"%{filters['q']}%"
            conditions.append(or_(
                Expense.description.ilike(needle),
                Expense.category.ilike(needle)
            ))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(Expense.date.desc(), Expense.id.desc())
    results = await db.execute(stmt)
    return list(results.scalars().all())


async def get_expense_by_id(db: AsyncSession, expense_id: int) -> Expense | None:
    repo = ExpenseRepository(db)
    return await repo.get(expense_id)


async def create_expense(db: AsyncSession, date: Any, category: str, description: str, amount: float, method: str = "cash") -> int:
    if isinstance(date, str):
        parsed_date = d_cls.fromisoformat(date)
    else:
        parsed_date = date
    from decimal import Decimal
    entity = Expense(
        date=parsed_date,
        category=category,
        description=description,
        amount=Decimal(str(amount)),
        payment_method=method
    )
    repo = ExpenseRepository(db)
    created = await repo.create(entity)
    return created.id


async def update_expense(db: AsyncSession, expense_id: int, date: Any, category: str, description: str, amount: float, method: str = "cash") -> None:
    repo = ExpenseRepository(db)
    entity = await repo.get(expense_id)
    if entity:
        if isinstance(date, str):
            entity.date = d_cls.fromisoformat(date)
        else:
            entity.date = date
        entity.category = category
        entity.description = description
        from decimal import Decimal
        entity.amount = Decimal(str(amount))
        entity.payment_method = method
        entity.updated_at = datetime.utcnow()
        await repo.update(entity)


async def delete_expense(db: AsyncSession, expense_id: int) -> None:
    repo = ExpenseRepository(db)
    await repo.delete(expense_id)


# ── Agrégations ──

async def expenses_total(db: AsyncSession, date_from: str | None = None, date_to: str | None = None) -> float:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0.0).label("total"))
    conditions = []
    if date_from and str(date_from).strip():
        conditions.append(Expense.date >= date_from)
    if date_to and str(date_to).strip():
        conditions.append(Expense.date <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    results = await db.execute(stmt)
    return float(results.scalar() or 0.0)


async def expenses_by_category(db: AsyncSession, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    stmt = select(
        Expense.category,
        func.coalesce(func.sum(Expense.amount), 0.0).label("total"),
        func.count().label("count")
    )
    conditions = []
    if date_from and str(date_from).strip():
        conditions.append(Expense.date >= date_from)
    if date_to and str(date_to).strip():
        conditions.append(Expense.date <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.group_by(Expense.category).order_by(func.sum(Expense.amount).desc())
    results = await db.execute(stmt)
    return [{"category": r[0], "total": r[1], "count": r[2]} for r in results.all()]


async def expenses_by_month(db: AsyncSession, limit: int = 12) -> list[dict]:
    month_expr = func.to_char(Expense.date, "YYYY-MM").label("month")
    stmt = select(
        month_expr,
        func.coalesce(func.sum(Expense.amount), 0.0).label("total"),
        func.count().label("count")
    ).group_by(month_expr).order_by(month_expr.desc()).limit(limit)
    results = await db.execute(stmt)
    return [{"month": r[0], "total": r[1], "count": r[2]} for r in results.all()]
