"""Modèles SQLModel pour le module Payments."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship

from app.core.model_utils import _now


class PaymentType(str, Enum):
    VERSEMENT = "versement"
    AVANCE = "avance"


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    sale_id: Optional[int] = Field(default=None, foreign_key="sales.id")
    raw_sale_id: Optional[int] = Field(default=None, foreign_key="raw_sales.id")
    sale_kind: Optional[str] = Field(default=None)
    payment_type: PaymentType = Field(default=PaymentType.VERSEMENT)
    allocation_meta: Optional[str] = Field(default=None)
    amount: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    payment_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    client: Optional["Client"] = Relationship(sa_relationship=relationship("Client", back_populates="payments"))
    sale: Optional["Sale"] = Relationship(sa_relationship=relationship("Sale", back_populates="payments"))
    raw_sale: Optional["RawSale"] = Relationship(sa_relationship=relationship("RawSale", back_populates="payments"))
