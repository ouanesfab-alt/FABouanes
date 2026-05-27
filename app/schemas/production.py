from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional
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



