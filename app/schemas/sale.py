from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class SaleCreate(BaseModel):
    item_key: str = Field(..., description="Format: 'finished:ID' ou 'raw:ID'")
    client_id: Optional[int] = Field(None, gt=0)
    quantity: float = Field(..., gt=0, le=999999.99)
    unit: str = Field(..., min_length=1, max_length=20)
    unit_price: float = Field(..., ge=0, le=99999999.99)
    sale_type: str = Field(..., pattern=r'^(cash|credit)$')
    amount_paid: float = Field(0.0, ge=0)
    sale_date: str = Field(..., description="Format YYYY-MM-DD")
    notes: Optional[str] = Field(None, max_length=2000)
    custom_item_name: Optional[str] = Field(None, max_length=200)

    @field_validator('item_key')
    @classmethod
    def validate_item_key(cls, v: str) -> str:
        if not re.match(r'^(finished|raw):\d+$', v):
            raise ValueError("Format item_key invalide. Attendu: 'finished:ID' ou 'raw:ID'")
        return v

    @field_validator('sale_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Format de date invalide. Attendu: YYYY-MM-DD")
        return v


class SaleUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0, le=999999.99)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    unit_price: Optional[float] = Field(None, ge=0, le=99999999.99)
    sale_type: Optional[str] = Field(None, pattern=r'^(cash|credit)$')
    amount_paid: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)
