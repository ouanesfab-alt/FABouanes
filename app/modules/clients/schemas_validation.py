from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

class ClientBaseSchema(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_credit: float = Field(default=0.0)

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

    @field_validator("opening_credit", mode="before")
    @classmethod
    def parse_credit(cls, val: any) -> float:
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
