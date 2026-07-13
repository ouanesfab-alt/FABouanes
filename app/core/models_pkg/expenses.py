"""Modèles SQLModel pour le module Expenses."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import Column, Numeric, BigInteger
from sqlmodel import SQLModel, Field
from pydantic import field_validator

from app.core.model_utils import _now


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    date: date
    category: str = Field(default="general", index=True)
    description: Optional[str] = Field(default=None)
    amount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))  # Migré float→Decimal (migration 0035)
    payment_method: str = Field(default="cash")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: Any) -> Decimal:
        """Coerce float/str retournés par SQLite en Decimal."""
        if not isinstance(v, Decimal):
            return Decimal(str(v))
        return v
