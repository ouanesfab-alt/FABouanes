from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
from datetime import date

from app.modules.catalog.api.schemas import parse_numeric


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

            # Parse client_id
            c_id = data.get("client_id")
            if c_id == "" or c_id is None:
                raise ValueError("Choisis un client.")
            try:
                data["client_id"] = int(c_id)
            except ValueError:
                raise ValueError("Choisis un client.")

            # Parse payment_type
            p_type = data.get("payment_type")
            if p_type:
                data["payment_type"] = p_type.strip()
            else:
                data["payment_type"] = "versement"

        return data
