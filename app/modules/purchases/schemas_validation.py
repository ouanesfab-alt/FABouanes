from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Any
from datetime import date

from app.modules.catalog.schemas_validation import parse_numeric


class PurchaseLineSchema(BaseModel):
    raw_material_id: str = Field(..., min_length=3)  # e.g. "raw:1" or "finished:2"
    quantity: float
    unit: str = Field("kg", min_length=1)
    unit_price: float
    custom_item_name: Optional[str] = Field(default="")

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def parse_fields(cls, val: Any) -> float:
        return parse_numeric(val)

    @field_validator("raw_material_id")
    @classmethod
    def validate_raw_material_id(cls, val: str) -> str:
        if ":" not in val:
            raise ValueError("L'article sélectionné est invalide.")
        parts = val.split(":", 1)
        if parts[0] not in {"finished", "raw"} or not parts[1].isdigit():
            raise ValueError("L'article sélectionné est invalide.")
        return val


class PurchaseFormSchema(BaseModel):
    supplier_id: Optional[int] = Field(default=None)
    purchase_date: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default="")
    lines: List[PurchaseLineSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def pre_validate(cls, data: Any) -> Any:
        if isinstance(data, dict) or hasattr(data, "get"):
            if not isinstance(data, dict):
                if hasattr(data, "getlist"):
                    new_data = {}
                    for k in data.keys():
                        if k.endswith("[]") or k in {"raw_material_id", "quantity", "unit", "unit_price", "custom_item_name"}:
                            new_data[k] = data.getlist(k)
                        else:
                            new_data[k] = data.get(k)
                    data = new_data
                else:
                    data = dict(data)

            # Parse supplier_id
            s_id = data.get("supplier_id")
            if s_id == "" or s_id is None:
                data["supplier_id"] = None
            else:
                try:
                    data["supplier_id"] = int(s_id)
                except ValueError:
                    data["supplier_id"] = None

            # Parse date
            p_date = data.get("purchase_date")
            if not p_date:
                data["purchase_date"] = date.today()

            # Reconstruct lines from lists if it comes from raw form dict
            if "raw_material_id[]" in data or "raw_material_id" in data:
                raw_material_ids = data.get("raw_material_id[]") or data.get("raw_material_id")
                if not isinstance(raw_material_ids, list):
                    raw_material_ids = [raw_material_ids] if raw_material_ids else []
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
                line_count = max(len(raw_material_ids), len(quantities), len(units), len(unit_prices), len(custom_names))
                for idx in range(line_count):
                    ik = raw_material_ids[idx] if idx < len(raw_material_ids) else None
                    q = quantities[idx] if idx < len(quantities) else None
                    u = units[idx] if idx < len(units) else "kg"
                    up = unit_prices[idx] if idx < len(unit_prices) else None
                    cn = custom_names[idx] if idx < len(custom_names) else ""

                    if ik or q or up:
                        lines.append({
                            "raw_material_id": ik,
                            "quantity": q,
                            "unit": u,
                            "unit_price": up,
                            "custom_item_name": cn
                        })
                data["lines"] = lines
        return data

    @field_validator("purchase_date", mode="before")
    @classmethod
    def parse_purchase_date(cls, val: Any) -> date:
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return date.fromisoformat(val.strip())
            except ValueError:
                pass
        return date.today()

    @field_validator("purchase_date")
    @classmethod
    def validate_date(cls, val: date) -> date:
        if val > date.today():
            raise ValueError("La date d'achat ne peut pas être dans le futur.")
        return val
