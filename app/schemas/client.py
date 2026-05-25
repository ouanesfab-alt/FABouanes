from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nom du client")
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    opening_credit: Decimal = Field(Decimal("0.0000"), ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom du client ne peut pas être vide.")
        return v.strip()

    class Config:
        json_encoders = {Decimal: str}


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    opening_credit: Optional[Decimal] = Field(None, ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Le nom du client ne peut pas être vide.")
        return v.strip() if v else v

    class Config:
        json_encoders = {Decimal: str}

