"""Modèles SQLModel pour le module Purchases."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship

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

    # Relationships
    purchases: list[Purchase] = Relationship(sa_relationship=relationship("Purchase", back_populates="supplier"))
    purchase_documents: list[PurchaseDocument] = Relationship(sa_relationship=relationship("PurchaseDocument", back_populates="supplier"))


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

    # Relationships
    supplier: Optional[Supplier] = Relationship(sa_relationship=relationship("Supplier", back_populates="purchases"))
    raw_material: Optional[RawMaterial] = Relationship(sa_relationship=relationship("RawMaterial", back_populates="purchases"))
    finished_product: Optional[FinishedProduct] = Relationship(sa_relationship=relationship("FinishedProduct", back_populates="purchases"))


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

    # Relationships
    supplier: Optional[Supplier] = Relationship(sa_relationship=relationship("Supplier", back_populates="purchase_documents"))
