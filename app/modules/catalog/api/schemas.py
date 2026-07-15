from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Any


def parse_numeric(val: any) -> float:
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        f_val = float(val)
    else:
        try:
            cleaned = str(val).replace(",", ".").replace(" ", "").replace("\xa0", "").strip()
            f_val = float(cleaned)
        except (ValueError, TypeError) as e:
            raise ValueError("La valeur doit être un nombre valide.") from e
    if f_val < 0:
        raise ValueError("La valeur ne peut pas être négative.")
    return f_val


class RawMaterialCreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field("kg", min_length=1)
    stock_qty: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    alert_threshold: float = Field(default=0.0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas être vide.")
        return cleaned

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("L'unité ne peut pas être vide.")
        return cleaned

    @field_validator("stock_qty", "avg_cost", "sale_price", "alert_threshold", mode="before")
    @classmethod
    def parse_fields(cls, val: any) -> float:
        return parse_numeric(val)


class RawMaterialUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    stock_qty: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    alert_threshold: float = Field(default=0.0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas être vide.")
        return cleaned

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("L'unité ne peut pas être vide.")
        return cleaned

    @field_validator("stock_qty", "avg_cost", "sale_price", "alert_threshold", mode="before")
    @classmethod
    def parse_fields(cls, val: any) -> float:
        return parse_numeric(val)


class FinishedProductCreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    default_unit: str = Field("kg", min_length=1)
    stock_qty: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)

    @model_validator(mode="before")
    @classmethod
    def populate_default_unit(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "unit" in data and "default_unit" not in data:
                data["default_unit"] = data["unit"]
        return data

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas être vide.")
        return cleaned

    @field_validator("default_unit")
    @classmethod
    def clean_unit(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("L'unité ne peut pas être vide.")
        return cleaned

    @field_validator("stock_qty", "sale_price", "avg_cost", mode="before")
    @classmethod
    def parse_fields(cls, val: any) -> float:
        return parse_numeric(val)


class FinishedProductUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    default_unit: str = Field(..., min_length=1)
    stock_qty: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)

    @model_validator(mode="before")
    @classmethod
    def populate_default_unit(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "unit" in data and "default_unit" not in data:
                data["default_unit"] = data["unit"]
        return data

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom ne peut pas être vide.")
        return cleaned

    @field_validator("default_unit")
    @classmethod
    def clean_unit(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("L'unité ne peut pas être vide.")
        return cleaned

    @field_validator("stock_qty", "sale_price", "avg_cost", mode="before")
    @classmethod
    def parse_fields(cls, val: any) -> float:
        return parse_numeric(val)


class RecipeItemSchema(BaseModel):
    raw_material_id: int
    quantity: float

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_quantity(cls, val: any) -> float:
        f_val = parse_numeric(val)
        if f_val <= 0:
            raise ValueError("La quantité doit être supérieure à 0.")
        return f_val


class RecipeCreateSchema(BaseModel):
    finished_product_id: int
    name: str = Field(..., min_length=1)
    notes: Optional[str] = Field(default="")
    items: List[RecipeItemSchema] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def clean_name(cls, val: str) -> str:
        cleaned = str(val).strip()
        if not cleaned:
            raise ValueError("Le nom de la recette ne peut pas être vide.")
        return cleaned
