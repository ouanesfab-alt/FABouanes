from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class PaymentCreate(BaseModel):
    client_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, le=Decimal("99999999.99"))
    payment_type: str = Field('versement', pattern=r'^(versement|avance)$')
    payment_date: str = Field(..., description="Format YYYY-MM-DD")
    sale_id: Optional[int] = Field(None, gt=0)
    raw_sale_id: Optional[int] = Field(None, gt=0)
    sale_kind: Optional[str] = Field(None, pattern=r'^(finished|raw)$')
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator('payment_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Format de date invalide. Attendu: YYYY-MM-DD")
        return v

    class Config:
        json_encoders = {Decimal: str}


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    payment_type: Optional[str] = Field(None, pattern=r'^(versement|avance)$')
    notes: Optional[str] = Field(None, max_length=2000)

    class Config:
        json_encoders = {Decimal: str}

