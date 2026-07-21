"""Modèles SQLModel pour le module Production."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship
from pydantic import field_validator

if TYPE_CHECKING:
    from app.core.models_pkg.catalog import FinishedProduct, RawMaterial


from app.core.model_utils import _now


class ProductionBatch(SQLModel, table=True):
    __tablename__ = "production_batches"

    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    output_quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    production_cost: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    unit_cost: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    production_date: date
    notes: Optional[str] = Field(default=None)

    # Relationships
    finished_product: Optional["FinishedProduct"] = Relationship(sa_relationship=relationship("FinishedProduct"))
    items: list["ProductionBatchItem"] = Relationship(sa_relationship=relationship("ProductionBatchItem", back_populates="batch"))

    @field_validator("production_date", mode="before")
    @classmethod
    def _coerce_production_date(cls, v: Any) -> date:
        """Coerce une chaîne ISO retournée par SQLite en objet date."""
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    @field_validator("output_quantity", "production_cost", "unit_cost", mode="before")
    @classmethod
    def _coerce_decimals(cls, v: Any) -> Decimal:
        """Coerce float/str retournés par SQLite/Postgres en Decimal."""
        if v is None:
            return Decimal("0.00")
        if not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class ProductionBatchItem(SQLModel, table=True):
    __tablename__ = "production_batch_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="production_batches.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    unit_cost_snapshot: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    line_cost: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))

    # Relationships
    batch: Optional["ProductionBatch"] = Relationship(sa_relationship=relationship("ProductionBatch", back_populates="items"))
    raw_material: Optional["RawMaterial"] = Relationship(sa_relationship=relationship("RawMaterial"))

    @field_validator("quantity", "unit_cost_snapshot", "line_cost", mode="before")
    @classmethod
    def _coerce_decimals(cls, v: Any) -> Decimal:
        """Coerce float/str retournés par SQLite/Postgres en Decimal."""
        if v is None:
            return Decimal("0.00")
        if not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class SavedRecipe(SQLModel, table=True):
    __tablename__ = "saved_recipes"

    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    name: str
    notes: Optional[str] = Field(default=None)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    finished_product: Optional["FinishedProduct"] = Relationship(sa_relationship=relationship("FinishedProduct"))
    items: list["SavedRecipeItem"] = Relationship(sa_relationship=relationship("SavedRecipeItem", back_populates="recipe"))


class SavedRecipeItem(SQLModel, table=True):
    __tablename__ = "saved_recipe_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="saved_recipes.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 2)))
    position: int = Field(default=0)

    # Relationships
    recipe: Optional["SavedRecipe"] = Relationship(sa_relationship=relationship("SavedRecipe", back_populates="items"))
    raw_material: Optional["RawMaterial"] = Relationship(sa_relationship=relationship("RawMaterial"))

    @field_validator("quantity", mode="before")
    @classmethod
    def _coerce_decimals(cls, v: Any) -> Decimal:
        """Coerce float/str retournés par SQLite/Postgres en Decimal."""
        if v is None:
            return Decimal("0.00")
        if not isinstance(v, Decimal):
            return Decimal(str(v))
        return v
