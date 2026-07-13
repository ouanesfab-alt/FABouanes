"""Modèles SQLModel pour le module Purchases."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="suppliers.id")
    document_id: Optional[int] = Field(default=None)
    raw_material_id: Optional[int] = Field(default=None, foreign_key="raw_materials.id")
    finished_product_id: Optional[int] = Field(default=None, foreign_key="finished_products.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    unit: str = Field(default="kg")
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    purchase_date: date
    notes: Optional[str] = Field(default=None)
    custom_item_name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class PurchaseDocument(SQLModel, table=True):
    __tablename__ = "purchase_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="suppliers.id")
    doc_number: str = Field(unique=True)
    total: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    purchase_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
