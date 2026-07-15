from __future__ import annotations

import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


class ExpenseBaseSchema(BaseModel):
    date: datetime.date = Field(..., description="Date de la dépense (format YYYY-MM-DD)")
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
    ] = Field("general", description="Catégorie (general, transport, loyer, salaires...)")
    description: Optional[str] = Field(None, description="Description ou note descriptive de la charge")
    amount: float = Field(default=0.0, gt=0.0, description="Montant de la dépense")
    payment_method: Literal["cash", "cheque", "virement", "autre"] = Field("cash", description="Moyen de paiement (cash, cheque, virement, autre)")

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
            cleaned = str(val).replace(",", ".").replace(" ", "").strip()
            return float(cleaned)
        except (ValueError, TypeError) as e:
            raise ValueError("Le montant doit etre un nombre valide.") from e


class ExpenseCreateSchema(ExpenseBaseSchema):
    pass


class ExpenseUpdateSchema(ExpenseBaseSchema):
    pass


class ExpenseOutSchema(ExpenseBaseSchema):
    id: int = Field(..., description="Identifiant unique de la dépense")


class ExpensesListResponse(BaseModel):
    success: bool = Field(True, description="Indique si la requête a réussi")
    data: List[ExpenseOutSchema] = Field(..., description="Liste des dépenses")
    meta: Optional[dict] = Field(None, description="Métadonnées de pagination")


class ExpenseDetailResponse(BaseModel):
    success: bool = Field(True, description="Indique si la requête a réussi")
    data: ExpenseOutSchema = Field(..., description="Détails de la dépense")


class ErrorResponseSchema(BaseModel):
    success: bool = Field(False, description="Indique si la requête a échoué")
    error: dict = Field(..., description="Détails de l'erreur avec codes et messages")
