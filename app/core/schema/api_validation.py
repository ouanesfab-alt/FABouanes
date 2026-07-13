from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Union

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



class ProductionCreateSchema(BaseModel):
    finished_product_id: int = Field(..., description="ID du produit fini")
    output_quantity: Decimal = Field(..., gt=0, description="Quantité produite")
    production_date: Optional[date] = Field(default=None, description="Date de production (YYYY-MM-DD)")
    notes: Optional[str] = Field(default="", description="Notes additionnelles")
    recipe_name: Optional[str] = Field(default="", description="Nom de la recette optionnel")
    save_recipe: Optional[Union[bool, int, str]] = Field(default=0, description="Sauvegarder comme recette")
    raw_material_ids: Optional[List[int]] = Field(default=None, alias="raw_material_id[]", description="Liste des IDs de matières premières")
    quantities: Optional[List[Decimal]] = Field(default=None, alias="quantity[]", description="Liste des quantités consommées")

    model_config = ConfigDict(populate_by_name=True)


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
