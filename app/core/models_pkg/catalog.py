"""Modèles SQLModel pour le module Catalog (matières premières, produits finis, stock)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship

from app.core.model_utils import _now


class RawMaterial(SQLModel, table=True):
    __tablename__ = "raw_materials"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    unit: str = Field(default="kg")
    stock_qty: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    avg_cost: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    sale_price: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    alert_threshold: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    threshold_qty: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    raw_sales: list[RawSale] = Relationship(sa_relationship=relationship("RawSale", back_populates="raw_material"))
    purchases: list[Purchase] = Relationship(sa_relationship=relationship("Purchase", back_populates="raw_material"))


class FinishedProduct(SQLModel, table=True):
    __tablename__ = "finished_products"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    default_unit: str = Field(default="kg")
    stock_qty: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    sale_price: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    avg_cost: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    alert_threshold: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    sales: list[Sale] = Relationship(sa_relationship=relationship("Sale", back_populates="finished_product"))
    purchases: list[Purchase] = Relationship(sa_relationship=relationship("Purchase", back_populates="finished_product"))


class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_kind: str
    item_id: int
    direction: str
    quantity: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    unit: Optional[str] = Field(default=None)
    stock_before: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    stock_after: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    reason: Optional[str] = Field(default=None)
    reference_type: Optional[str] = Field(default=None)
    reference_id: Optional[int] = Field(default=None)
    created_by_username: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)


class StockAlert(SQLModel, table=True):
    __tablename__ = "stock_alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_type: str
    product_id: int
    product_name: str
    current_qty: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    threshold_qty: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    triggered_at: datetime = Field(default_factory=_now)
    acknowledged_at: Optional[datetime] = Field(default=None)
