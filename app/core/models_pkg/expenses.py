"""Modèles SQLModel pour le module Expenses."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric, BigInteger
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    date: date
    category: str = Field(default="general", index=True)
    description: Optional[str] = Field(default=None)
    amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))  # Migré float→Decimal (migration 0035)
    payment_method: str = Field(default="cash")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
