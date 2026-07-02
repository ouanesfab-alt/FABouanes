"""Modèles SQLModel pour le module Production."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class ProductionBatch(SQLModel, table=True):
    __tablename__ = "production_batches"

    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    output_quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    production_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    unit_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    production_date: date
    notes: Optional[str] = Field(default=None)


class ProductionBatchItem(SQLModel, table=True):
    __tablename__ = "production_batch_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="production_batches.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit_cost_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    line_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))


class SavedRecipe(SQLModel, table=True):
    __tablename__ = "saved_recipes"

    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    name: str
    notes: Optional[str] = Field(default=None)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SavedRecipeItem(SQLModel, table=True):
    __tablename__ = "saved_recipe_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="saved_recipes.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    position: int = Field(default=0)
