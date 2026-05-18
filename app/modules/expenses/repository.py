"""Requêtes SQL du module Dépenses & Charges, implémentées avec SQLAlchemy Core 2.0."""
from __future__ import annotations

from typing import Any
from sqlalchemy import (
    Table, MetaData, Column, BigInteger, Date, String, Double, DateTime,
    select, insert, update, delete, and_, or_, func
)

from app.core.db_access import execute_sa, query_sa

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

# ── Table Metadata (SQLAlchemy 2.0) ──

metadata = MetaData()
expenses = Table(
    "expenses",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("date", Date, nullable=False),
    Column("category", String, nullable=False, default="general"),
    Column("description", String),
    Column("amount", Double, nullable=False, default=0.0),
    Column("payment_method", String, default="cash"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)

# ── CRUD ──

def get_all_expenses(filters: dict[str, Any] | None = None) -> list[dict]:
    stmt = select(expenses)
    conditions = []
    if filters:
        if filters.get("category"):
            conditions.append(expenses.c.category == filters["category"])
        if filters.get("date_from") and str(filters["date_from"]).strip():
            conditions.append(expenses.c.date >= filters["date_from"])
        if filters.get("date_to") and str(filters["date_to"]).strip():
            conditions.append(expenses.c.date <= filters["date_to"])
        if filters.get("q") and str(filters["q"]).strip():
            needle = f"%{filters['q']}%"
            conditions.append(or_(
                expenses.c.description.ilike(needle),
                expenses.c.category.ilike(needle)
            ))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(expenses.c.date.desc(), expenses.c.id.desc())
    return [dict(row) for row in query_sa(stmt)]


def get_expense_by_id(expense_id: int) -> dict | None:
    stmt = select(expenses).where(expenses.c.id == expense_id)
    row = query_sa(stmt, one=True)
    return dict(row) if row else None


def create_expense(date: str, category: str, description: str, amount: float, method: str = "cash") -> int:
    stmt = insert(expenses).values(
        date=date,
        category=category,
        description=description,
        amount=amount,
        payment_method=method
    )
    return execute_sa(stmt)


def update_expense(expense_id: int, date: str, category: str, description: str, amount: float, method: str = "cash") -> None:
    stmt = update(expenses).where(expenses.c.id == expense_id).values(
        date=date,
        category=category,
        description=description,
        amount=amount,
        payment_method=method,
        updated_at=func.now()
    )
    execute_sa(stmt)


def delete_expense(expense_id: int) -> None:
    stmt = delete(expenses).where(expenses.c.id == expense_id)
    execute_sa(stmt)


# ── Agrégations ──

def expenses_total(date_from: str | None = None, date_to: str | None = None) -> float:
    stmt = select(func.coalesce(func.sum(expenses.c.amount), 0.0).label("total"))
    conditions = []
    if date_from and str(date_from).strip():
        conditions.append(expenses.c.date >= date_from)
    if date_to and str(date_to).strip():
        conditions.append(expenses.c.date <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    row = query_sa(stmt, one=True)
    return float(row["total"]) if row else 0.0


def expenses_by_category(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    stmt = select(
        expenses.c.category,
        func.coalesce(func.sum(expenses.c.amount), 0.0).label("total"),
        func.count().label("count")
    )
    conditions = []
    if date_from and str(date_from).strip():
        conditions.append(expenses.c.date >= date_from)
    if date_to and str(date_to).strip():
        conditions.append(expenses.c.date <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.group_by(expenses.c.category).order_by(func.sum(expenses.c.amount).desc())
    return [dict(row) for row in query_sa(stmt)]


def expenses_by_month(limit: int = 12) -> list[dict]:
    month_expr = func.to_char(expenses.c.date, "YYYY-MM").label("month")
    stmt = select(
        month_expr,
        func.coalesce(func.sum(expenses.c.amount), 0.0).label("total"),
        func.count().label("count")
    ).group_by(month_expr).order_by(month_expr.desc()).limit(limit)
    return [dict(row) for row in query_sa(stmt)]
