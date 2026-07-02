from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ClientValidationSchema(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = Field(default="")
    address: Optional[str] = Field(default="")
    notes: Optional[str] = Field(default="")
    opening_credit: Optional[Decimal] = Field(default=Decimal("0.0000"))

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Le nom du client ne peut pas être vide.")
        return str(value).strip()

    @field_validator("opening_credit", mode="before")
    @classmethod
    def clean_opening_credit(cls, value: object) -> Decimal:
        if value is None or value == "":
            return Decimal("0.0000")
        if isinstance(value, (int, float, Decimal)):
            val = Decimal(str(value))
        else:
            # Parse European decimal format (e.g. "1 500,50" -> 1500.50)
            cleaned = str(value).replace(" ", "").replace("\xa0", "").replace(",", ".")
            try:
                val = Decimal(cleaned)
            except Exception:
                raise ValueError("Le montant du crédit initial est invalide.")
        if val < 0:
            raise ValueError("Le crédit initial ne peut pas être négatif.")
        return val
