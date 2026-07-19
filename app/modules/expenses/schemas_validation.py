from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ExpenseBaseSchema(BaseModel):
    date: date
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
    ] = "general"
    description: str | None = None
    amount: float = Field(default=0.0, gt=0.0)
    payment_method: Literal["cash", "cheque", "virement", "autre"] = "cash"

    @field_validator("description")
    @classmethod
    def clean_description(cls, val: str | None) -> str | None:
        if val is None:
            return None
        cleaned = val.strip()
        return cleaned if cleaned else None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, val: any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if not val:
            return 0.0
        try:
            # Handle comma and space formatting from European forms
            cleaned = str(val).replace(",", ".").replace(" ", "").strip()
            return float(cleaned)
        except (ValueError, TypeError) as e:
            raise ValueError("Le montant doit etre un nombre valide.") from e


class ExpenseCreateSchema(ExpenseBaseSchema):
    pass


class ExpenseUpdateSchema(ExpenseBaseSchema):
    pass
