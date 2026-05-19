from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class PurchaseCreate(BaseModel):
    raw_material_id: Optional[int] = Field(None, gt=0)
    finished_product_id: Optional[int] = Field(None, gt=0)
    supplier_id: Optional[int] = Field(None, gt=0)
    quantity: float = Field(..., gt=0, le=999999.99)
    unit: str = Field('kg', min_length=1, max_length=20)
    unit_price: float = Field(..., ge=0, le=99999999.99)
    purchase_date: str = Field(..., description="Format YYYY-MM-DD")
    notes: Optional[str] = Field(None, max_length=2000)
    custom_item_name: Optional[str] = Field(None, max_length=200)

    @field_validator('purchase_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Format de date invalide. Attendu: YYYY-MM-DD")
        return v


class PurchaseUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0, le=999999.99)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0, le=99999999.99)
    notes: Optional[str] = Field(None, max_length=2000)
