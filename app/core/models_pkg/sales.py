"""Modèles SQLModel pour le module Sales."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class Sale(SQLModel, table=True):
    __tablename__ = "sales"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    sale_type: str
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    profit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RawSale(SQLModel, table=True):
    __tablename__ = "raw_sales"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    sale_type: str
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    profit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    custom_item_name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SaleDocument(SQLModel, table=True):
    __tablename__ = "sale_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    doc_number: str = Field(unique=True)
    sale_type: str
    total: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
