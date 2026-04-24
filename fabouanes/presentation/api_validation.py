from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class _BasePayload(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class AuthLoginPayload(_BasePayload):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=300)


class AuthRefreshPayload(_BasePayload):
    refresh_token: str = Field(min_length=1, max_length=1024)


class ClientCreatePayload(_BasePayload):
    name: str = Field(min_length=1, max_length=200)
    phone: str = ""
    address: str = ""
    notes: str = ""
    opening_credit: float | str | int = 0


class PurchaseCreatePayload(_BasePayload):
    raw_material_id: int | str
    quantity: float | str | int
    unit_price: float | str | int
    purchase_date: str | None = None
    unit: str = "kg"
    supplier_id: int | str | None = None
    notes: str = ""


class SaleCreatePayload(_BasePayload):
    item_key: str = Field(min_length=1, max_length=120)
    quantity: float | str | int
    unit_price: float | str | int
    sale_date: str | None = None
    unit: str = "kg"
    client_id: int | str | None = None
    notes: str = ""
    sale_type: str | None = None
    amount_paid: float | str | int | None = None


class PaymentCreatePayload(_BasePayload):
    client_id: int | str
    amount: float | str | int
    payment_type: str = "versement"
    payment_date: str | None = None
    notes: str = ""
    sale_link: str = ""

    @field_validator("payment_type")
    @classmethod
    def _normalize_payment_type(cls, value: str) -> str:
        normalized = str(value or "versement").strip().lower() or "versement"
        if normalized not in {"versement", "avance"}:
            return "versement"
        return normalized


def validate_payload(model_type: type[BaseModel], payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    try:
        model = model_type.model_validate(payload or {})
        return model.model_dump(exclude_none=True), None
    except ValidationError as exc:
        normalized_errors = [dict(item) for item in exc.errors()]
        return {}, normalized_errors
