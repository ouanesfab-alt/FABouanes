from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class ClientBaseSchema(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_credit: float = Field(default=0.0)
    credit_limit: Optional[Decimal] = Field(default=None)

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas etre vide.")
        return cleaned

    @field_validator("phone", "address", "notes")
    @classmethod
    def clean_strings(cls, val: str | None) -> str | None:
        if val is None:
            return None
        cleaned = str(val).strip()
        return cleaned if cleaned else None

    @field_validator("credit_limit", mode="before")
    @classmethod
    def clean_credit_limit(cls, val: Any) -> Decimal | None:
        if val is None or val == "":
            return None
        if isinstance(val, (int, float, Decimal)):
            d_val = Decimal(str(val))
        else:
            cleaned = str(val).replace(",", ".").replace(" ", "").replace("\xa0", "").strip()
            if not cleaned:
                return None
            try:
                d_val = Decimal(cleaned)
            except Exception:
                raise ValueError("Le plafond de crédit doit être un nombre valide.")
        if d_val < Decimal("0"):
            raise ValueError("Le plafond de crédit ne peut pas être négatif.")
        return d_val

    @field_validator("opening_credit", mode="before")
    @classmethod
    def parse_credit(cls, val: Any) -> float:
        if val is None or val == "":
            return 0.0
        if isinstance(val, (int, float)):
            f_val = float(val)
        else:
            try:
                cleaned = str(val).replace(",", ".").replace(" ", "").replace("\xa0", "").strip()
                f_val = float(cleaned)
            except (ValueError, TypeError) as e:
                raise ValueError("Le solde initial doit etre un nombre valide.") from e
        if f_val < 0:
            raise ValueError("Le crédit initial ne peut pas être négatif.")
        return f_val


class ClientCreateSchema(ClientBaseSchema):
    pass


class ClientUpdateSchema(ClientBaseSchema):
    pass


class ClientValidationSchema(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = Field(default="")
    address: Optional[str] = Field(default="")
    notes: Optional[str] = Field(default="")
    opening_credit: Optional[Decimal] = Field(default=Decimal("0.0000"))
    credit_limit: Optional[Decimal] = Field(default=None)

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
            cleaned = str(value).replace(" ", "").replace("\xa0", "").replace(",", ".")
            try:
                val = Decimal(cleaned)
            except Exception:
                raise ValueError("Le montant du crédit initial est invalide.")
        if val < 0:
            raise ValueError("Le crédit initial ne peut pas être négatif.")
        return val


class ClientHistoryRowSchema(BaseModel):
    operation_date: str
    designation: str
    montant_achat: Decimal
    montant_verse: Decimal
    solde_cumule: Decimal
    ordre_import: int
    source: str
    type_operation: str


class ClientHistoryResponseSchema(BaseModel):
    client_id: int
    rows: List[ClientHistoryRowSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


__all__ = [
    "ClientBaseSchema",
    "ClientCreateSchema",
    "ClientUpdateSchema",
    "ClientValidationSchema",
    "ClientHistoryRowSchema",
    "ClientHistoryResponseSchema",
]
