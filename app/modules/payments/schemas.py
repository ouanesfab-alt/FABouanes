from __future__ import annotations

from datetime import date
from decimal import Decimal
import re
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.catalog.schemas_validation import parse_numeric


class PaymentCreate(BaseModel):
    client_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, le=Decimal("99999999.99"))
    payment_type: str = Field("versement", pattern=r"^(versement|avance)$")
    payment_date: str = Field(..., description="Format YYYY-MM-DD")
    sale_id: Optional[int] = Field(None, gt=0)
    raw_sale_id: Optional[int] = Field(None, gt=0)
    sale_kind: Optional[str] = Field(None, pattern=r"^(finished|raw)$")
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("payment_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Format de date invalide. Attendu: YYYY-MM-DD")
        return v


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0, le=Decimal("99999999.99"))
    payment_type: Optional[str] = Field(None, pattern=r"^(versement|avance)$")
    notes: Optional[str] = Field(None, max_length=2000)


class PaymentCreateSchema(BaseModel):
    client_id: Union[int, str] = Field(..., description="ID du client")
    amount: Union[Decimal, str] = Field(..., description="Montant du paiement")
    payment_date: Optional[str] = Field(default=None, description="Date du versement (YYYY-MM-DD)")
    payment_type: Optional[str] = Field(default="versement", description="Type de paiement")
    sale_link: Optional[str] = Field(default="", description="Lien de la vente liée (kind:id)")
    notes: Optional[str] = Field(default="", description="Notes additionnelles")

    @field_validator("client_id", mode="before")
    @classmethod
    def clean_client_id(cls, value: object) -> int:
        if value is None or value == "":
            raise ValueError("Choisis un client.")
        try:
            return int(str(value).strip())
        except ValueError:
            raise ValueError("ID de client invalide.")

    @field_validator("amount", mode="before")
    @classmethod
    def clean_amount(cls, value: object) -> Decimal:
        if value is None or value == "":
            raise ValueError("Le montant est requis.")
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        cleaned = str(value).replace(" ", "").replace("\xa0", "").replace(",", ".")
        try:
            return Decimal(cleaned)
        except Exception:
            raise ValueError("Montant invalide.")


class PaymentFormSchema(BaseModel):
    client_id: int
    sale_link: Optional[str] = Field(default="")
    amount: float
    payment_date: date = Field(default_factory=date.today)
    payment_type: str = Field(default="versement")
    notes: Optional[str] = Field(default="")

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, val: Any) -> float:
        return parse_numeric(val)

    @field_validator("payment_date", mode="before")
    @classmethod
    def parse_payment_date(cls, val: Any) -> date:
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return date.fromisoformat(val.strip())
            except ValueError:
                pass
        return date.today()

    @field_validator("payment_date")
    @classmethod
    def validate_date(cls, val: date) -> date:
        if val > date.today():
            raise ValueError("La date de versement ne peut pas être dans le futur.")
        return val

    @model_validator(mode="before")
    @classmethod
    def pre_validate(cls, data: Any) -> Any:
        if isinstance(data, dict) or hasattr(data, "get"):
            if not isinstance(data, dict):
                data = dict(data)

            c_id = data.get("client_id")
            if c_id == "" or c_id is None:
                raise ValueError("Choisis un client.")
            try:
                data["client_id"] = int(c_id)
            except ValueError:
                raise ValueError("Choisis un client.")

            p_type = data.get("payment_type")
            if p_type:
                data["payment_type"] = p_type.strip()
            else:
                data["payment_type"] = "versement"

        return data


__all__ = [
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentCreateSchema",
    "PaymentFormSchema",
]
