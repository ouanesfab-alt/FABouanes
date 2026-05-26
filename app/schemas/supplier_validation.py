from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class SupplierValidationSchema(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = Field(default="")
    address: Optional[str] = Field(default="")
    notes: Optional[str] = Field(default="")

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Le nom du fournisseur ne peut pas être vide.")
        return str(value).strip()
