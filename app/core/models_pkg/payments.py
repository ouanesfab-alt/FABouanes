"""Modèles SQLModel pour le module Payments."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    sale_id: Optional[int] = Field(default=None, foreign_key="sales.id")
    raw_sale_id: Optional[int] = Field(default=None, foreign_key="raw_sales.id")
    sale_kind: Optional[str] = Field(default=None)
    payment_type: str = Field(default="versement")
    allocation_meta: Optional[str] = Field(default=None)
    amount: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    payment_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
