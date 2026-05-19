from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class RawMaterialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    unit: str = Field('kg', min_length=1, max_length=20)
    stock_qty: float = Field(0.0, ge=0)
    avg_cost: float = Field(0.0, ge=0)
    sale_price: float = Field(0.0, ge=0)
    alert_threshold: float = Field(0.0, ge=0)
    threshold_qty: float = Field(0.0, ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip()


class RawMaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    sale_price: Optional[float] = Field(None, ge=0)
    alert_threshold: Optional[float] = Field(None, ge=0)
    threshold_qty: Optional[float] = Field(None, ge=0)


class FinishedProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    default_unit: str = Field('kg', min_length=1, max_length=20)
    stock_qty: float = Field(0.0, ge=0)
    sale_price: float = Field(0.0, ge=0)
    avg_cost: float = Field(0.0, ge=0)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip()


class FinishedProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    default_unit: Optional[str] = Field(None, min_length=1, max_length=20)
    sale_price: Optional[float] = Field(None, ge=0)
