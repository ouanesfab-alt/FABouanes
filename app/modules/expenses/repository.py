"""Requêtes SQL du module Dépenses & Charges."""
from __future__ import annotations

from typing import Any

from app.core.db_access import execute_db, query_db


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


# ── CRUD ──

def get_all_expenses(filters: dict[str, Any] | None = None) -> list[dict]:
    sql = "SELECT * FROM expenses WHERE 1=1"
    params: list[Any] = []
    if filters:
        if filters.get("category"):
            sql += " AND category = ?"
            params.append(filters["category"])
        if filters.get("date_from"):
            sql += " AND date >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            sql += " AND date <= ?"
            params.append(filters["date_to"])
        if filters.get("q"):
            sql += " AND (description LIKE ? OR category LIKE ?)"
            needle = f"%{filters['q']}%"
            params.extend([needle, needle])
    sql += " ORDER BY date DESC, id DESC"
    return [dict(row) for row in query_db(sql, tuple(params))]


def get_expense_by_id(expense_id: int) -> dict | None:
    row = query_db("SELECT * FROM expenses WHERE id = ?", (expense_id,), one=True)
    return dict(row) if row else None


def create_expense(date: str, category: str, description: str, amount: float, method: str = "cash") -> int:
    return execute_db(
        "INSERT INTO expenses (date, category, description, amount, payment_method) VALUES (?,?,?,?,?)",
        (date, category, description, amount, method),
    )


def update_expense(expense_id: int, date: str, category: str, description: str, amount: float, method: str = "cash") -> None:
    execute_db(
        "UPDATE expenses SET date=?, category=?, description=?, amount=?, payment_method=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (date, category, description, amount, method, expense_id),
    )


def delete_expense(expense_id: int) -> None:
    execute_db("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ── Agrégations ──

def expenses_total(date_from: str | None = None, date_to: str | None = None) -> float:
    sql = "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE 1=1"
    params: list[Any] = []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    row = query_db(sql, tuple(params), one=True)
    return float(row["total"]) if row else 0.0


def expenses_by_category(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    sql = "SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count FROM expenses WHERE 1=1"
    params: list[Any] = []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    sql += " GROUP BY category ORDER BY total DESC"
    return [dict(row) for row in query_db(sql, tuple(params))]

def expenses_by_month(limit: int = 12) -> list[dict]:
    rows = query_db(
        """SELECT substr(date::text, 1, 7) AS month,
                  COALESCE(SUM(amount), 0) AS total,
                  COUNT(*) AS count
           FROM expenses
           GROUP BY substr(date::text, 1, 7)
           ORDER BY month DESC
           LIMIT ?""",
        (limit,),
    )
    return [dict(r) for r in rows]
