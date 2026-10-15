from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ExpenseBaseSchema(BaseModel):
    date: _dt.date = Field(..., description="Date de la dépense (format YYYY-MM-DD)")
    category: Literal[
        "general",
        "transport",
        "fournitures",
        "loyer",
        "salaires",
        "maintenance",
        "telecom",
        "energie",
        "impots",
        "autre",
    ] = Field(default="general", description="Catégorie de la dépense")
    description: str | None = Field(default=None, description="Description de la charge")
    amount: Decimal = Field(default=Decimal("0.00"), gt=Decimal("0.00"), description="Montant financier de la dépense")
    payment_method: Literal["cash", "cheque", "virement", "autre"] = Field(
        default="cash", description="Moyen de paiement"
    )

    @field_validator("description")
    @classmethod
    def clean_description(cls, val: str | None) -> str | None:
        if val is None:
            return None
        cleaned = val.strip()
        return cleaned if cleaned else None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, val: Any) -> Decimal:
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        if not val:
            return Decimal("0.00")
        try:
            # Handle comma and space formatting from European/French forms
            cleaned = str(val).replace(",", ".").replace(" ", "").strip()
            return Decimal(cleaned)
        except (ValueError, TypeError) as e:
            raise ValueError("Le montant doit être un nombre valide.") from e


class ExpenseCreateSchema(ExpenseBaseSchema):
    pass


class ExpenseUpdateSchema(ExpenseBaseSchema):
    pass


class ExpenseOutSchema(ExpenseBaseSchema):
    id: int = Field(..., description="Identifiant unique de la dépense")
    amount: float = Field(default=0.0, description="Montant financier de la dépense")

    @field_validator("amount", mode="before")
    @classmethod
    def convert_amount_to_float(cls, val: Any) -> float:
        return float(val) if val is not None else 0.0
