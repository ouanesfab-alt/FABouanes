from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Any
from datetime import date

from app.modules.catalog.schemas_validation import parse_numeric


class SaleLineSchema(BaseModel):
    item_key: str = Field(..., min_length=3)  # e.g. "finished:1" or "raw:2"
    quantity: float
    unit: str = Field("kg", min_length=1)
    unit_price: float
    custom_item_name: Optional[str] = Field(default="")

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def parse_fields(cls, val: Any) -> float:
        return parse_numeric(val)

    @field_validator("item_key")
    @classmethod
    def validate_item_key(cls, val: str) -> str:
        if ":" not in val:
            raise ValueError("L'article sélectionné est invalide.")
        parts = val.split(":", 1)
        if parts[0] not in {"finished", "raw"} or not parts[1].isdigit():
            raise ValueError("L'article sélectionné est invalide.")
        return val


class SaleFormSchema(BaseModel):
    client_id: Optional[int] = Field(default=None)
    sale_date: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default="")
    lines: List[SaleLineSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def pre_validate(cls, data: Any) -> Any:
        if isinstance(data, dict) or hasattr(data, "get"):
            if not isinstance(data, dict):
                if hasattr(data, "getlist"):
                    new_data = {}
                    for k in data.keys():
                        if k.endswith("[]") or k in {"item_key", "quantity", "unit", "unit_price", "custom_item_name"}:
                            new_data[k] = data.getlist(k)
                        else:
                            new_data[k] = data.get(k)
                    data = new_data
                else:
                    data = dict(data)

            # Parse client_id
            c_id = data.get("client_id")
            if c_id == "" or c_id is None:
                data["client_id"] = None
            else:
                try:
                    data["client_id"] = int(c_id)
                except ValueError:
                    data["client_id"] = None

            # Parse date
            s_date = data.get("sale_date")
            if not s_date:
                data["sale_date"] = date.today()

            # Reconstruct lines from lists if it comes from raw form dict
            if "item_key[]" in data or "item_key" in data:
                item_keys = data.get("item_key[]") or data.get("item_key")
                if not isinstance(item_keys, list):
                    item_keys = [item_keys] if item_keys else []
                quantities = data.get("quantity[]") or data.get("quantity")
                if not isinstance(quantities, list):
                    quantities = [quantities] if quantities else []
                units = data.get("unit[]") or data.get("unit")
                if not isinstance(units, list):
                    units = [units] if units else []
                unit_prices = data.get("unit_price[]") or data.get("unit_price")
                if not isinstance(unit_prices, list):
                    unit_prices = [unit_prices] if unit_prices else []
                custom_names = data.get("custom_item_name[]") or data.get("custom_item_name")
                if not isinstance(custom_names, list):
                    custom_names = [custom_names] if custom_names else []

                lines = []
                line_count = max(len(item_keys), len(quantities), len(units), len(unit_prices), len(custom_names))
                for idx in range(line_count):
                    ik = item_keys[idx] if idx < len(item_keys) else None
                    q = quantities[idx] if idx < len(quantities) else None
                    u = units[idx] if idx < len(units) else "kg"
                    up = unit_prices[idx] if idx < len(unit_prices) else None
                    cn = custom_names[idx] if idx < len(custom_names) else ""

                    if ik or q or up:
                        lines.append({
                            "item_key": ik,
                            "quantity": q,
                            "unit": u,
                            "unit_price": up,
                            "custom_item_name": cn
                        })
                print(f"SCHEMA DEBUG: parsed lines={lines}")
                data["lines"] = lines
        return data
    @field_validator("sale_date", mode="before")
    @classmethod
    def parse_sale_date(cls, val: Any) -> date:
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return date.fromisoformat(val.strip())
            except ValueError:
                pass
        return date.today()

    @field_validator("sale_date")
    @classmethod
    def validate_date(cls, val: date) -> date:
        if val > date.today():
            raise ValueError("La date de vente ne peut pas être dans le futur.")
        return val
