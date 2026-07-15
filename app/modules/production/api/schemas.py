from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Union, List
from datetime import date
import re


class ProductionBatchItemInput(BaseModel):
    raw_material_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0, le=Decimal("999999.99"))


class ProductionBatchCreate(BaseModel):
    finished_product_id: int = Field(..., gt=0)
    output_quantity: Decimal = Field(..., gt=0, le=Decimal("999999.99"))
    production_date: str = Field(..., description="Format YYYY-MM-DD")
    notes: Optional[str] = Field(None, max_length=2000)
    items: list[ProductionBatchItemInput] = Field(..., min_length=1)

    @field_validator('production_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Format de date invalide. Attendu: YYYY-MM-DD")
        return v


class ProductionCreateSchema(BaseModel):
    finished_product_id: int = Field(..., description="ID du produit fini")
    output_quantity: Decimal = Field(..., gt=0, description="Quantité produite")
    production_date: Optional[date] = Field(default=None, description="Date de production (YYYY-MM-DD)")
    notes: Optional[str] = Field(default="", description="Notes additionnelles")
    recipe_name: Optional[str] = Field(default="", description="Nom de la recette optionnel")
    save_recipe: Optional[Union[bool, int, str]] = Field(default=0, description="Sauvegarder comme recette")
    raw_material_ids: Optional[List[int]] = Field(default=None, alias="raw_material_id[]", description="Liste des IDs de matières premières")
    quantities: Optional[List[Decimal]] = Field(default=None, alias="quantity[]", description="Liste des quantités consommées")

    model_config = ConfigDict(populate_by_name=True)
