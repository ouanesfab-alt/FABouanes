"""Modèles SQLModel pour le module Sales."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Numeric, String
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship

from app.core.model_utils import _now


class SaleType(str, Enum):
    CASH = "cash"
    CREDIT = "credit"


class Sale(SQLModel, table=True):
    __tablename__ = "sales"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    sale_type: SaleType = Field(sa_column=Column(String, nullable=False))
    amount_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    balance_due: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    profit_amount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    client: Optional["Client"] = Relationship(sa_relationship=relationship("Client", back_populates="sales"))
    finished_product: Optional["FinishedProduct"] = Relationship(sa_relationship=relationship("FinishedProduct", back_populates="sales"))
    payments: list["Payment"] = Relationship(sa_relationship=relationship("Payment", back_populates="sale"))


class RawSale(SQLModel, table=True):
    __tablename__ = "raw_sales"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    sale_type: SaleType = Field(sa_column=Column(String, nullable=False))
    amount_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    balance_due: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    profit_amount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    custom_item_name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    client: Optional["Client"] = Relationship(sa_relationship=relationship("Client", back_populates="raw_sales"))
    raw_material: Optional["RawMaterial"] = Relationship(sa_relationship=relationship("RawMaterial", back_populates="raw_sales"))
    payments: list["Payment"] = Relationship(sa_relationship=relationship("Payment", back_populates="raw_sale"))


class SaleDocument(SQLModel, table=True):
    __tablename__ = "sale_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    doc_number: str = Field(unique=True)
    sale_type: SaleType = Field(sa_column=Column(String, nullable=False))
    total: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    amount_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    balance_due: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    client: Optional["Client"] = Relationship(sa_relationship=relationship("Client", back_populates="sale_documents"))
