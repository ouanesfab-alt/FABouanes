from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class RawMaterialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    unit: str = Field('kg', min_length=1, max_length=20)
    stock_qty: Decimal = Field(Decimal("0.0000"), ge=0)
    avg_cost: Decimal = Field(Decimal("0.0000"), ge=0)
    sale_price: Decimal = Field(Decimal("0.0000"), ge=0)
    alert_threshold: Decimal = Field(Decimal("0.0000"), ge=0)
    threshold_qty: Decimal = Field(Decimal("0.0000"), ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip()

    class Config:
        json_encoders = {Decimal: str}


class RawMaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    sale_price: Optional[Decimal] = Field(None, ge=0)
    alert_threshold: Optional[Decimal] = Field(None, ge=0)
    threshold_qty: Optional[Decimal] = Field(None, ge=0)

    class Config:
        json_encoders = {Decimal: str}


class FinishedProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    default_unit: str = Field('kg', min_length=1, max_length=20)
    stock_qty: Decimal = Field(Decimal("0.0000"), ge=0)
    sale_price: Decimal = Field(Decimal("0.0000"), ge=0)
    avg_cost: Decimal = Field(Decimal("0.0000"), ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip()

    class Config:
        json_encoders = {Decimal: str}


class FinishedProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    default_unit: Optional[str] = Field(None, min_length=1, max_length=20)
    sale_price: Optional[Decimal] = Field(None, ge=0)

    class Config:
        json_encoders = {Decimal: str}

