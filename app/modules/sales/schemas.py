from __future__ import annotations

from decimal import Decimal
import inspect
import math
from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text

from app.core.exceptions import NotFoundError, ValidationError
from app.core.models import Client, FinishedProduct, RawMaterial
from app.modules.catalog.schemas import parse_decimal
from app.modules.catalog.stock_service import qty_to_kg


class SaleLineSchema(BaseModel):
    item_key: str = Field(..., min_length=3)  # e.g. "finished:1" or "raw:2"
    quantity: Decimal
    unit: str = Field("kg", min_length=1)
    unit_price: Decimal
    custom_item_name: Optional[str] = Field(default="")

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def parse_fields(cls, val: Any) -> Decimal:
        return parse_decimal(val)

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
    sale_type: Optional[str] = Field(default=None)
    sale_date: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default="")
    allow_overlimit: bool = Field(default=False)
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

            # Parse sale_type
            s_type = data.get("sale_type")
            if s_type:
                st = str(s_type).strip().lower()
                if st in {"cash", "comptant", "espece", "especes"}:
                    data["sale_type"] = "cash"
                elif st in {"credit", "crédit", "dette", "dettes", "terme"}:
                    data["sale_type"] = "credit"
                else:
                    data["sale_type"] = None
            else:
                data["sale_type"] = None

            # Parse allow_overlimit
            ao = data.get("allow_overlimit") or data.get("force_credit")
            if ao in {"1", "true", "True", True, "on", "yes"}:
                data["allow_overlimit"] = True
            elif ao in {"0", "false", "False", False, "off", "no"} or ao is None:
                data["allow_overlimit"] = False

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
                        lines.append(
                            {"item_key": ik, "quantity": q, "unit": u, "unit_price": up, "custom_item_name": cn}
                        )
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


class SalesValidator:
    """Valide les règles métier du module Sales."""

    @staticmethod
    async def validate_client(client_id: int | None, session: AsyncSession) -> None:
        if client_id:
            client = await session.get(Client, client_id)
            if not client:
                raise NotFoundError("Client", client_id)

    @staticmethod
    async def validate_client_credit_limit(
        client_id: int | None,
        additional_debt: Decimal,
        session: AsyncSession,
        allow_overlimit: bool = False,
    ) -> None:
        if not client_id or additional_debt <= Decimal("0.00") or allow_overlimit:
            return

        client_res = session.get(Client, client_id)
        if inspect.isawaitable(client_res):
            client = await client_res
        else:
            client = client_res

        if not client:
            return

        credit_limit = getattr(client, "credit_limit", None)
        if not credit_limit or inspect.isawaitable(credit_limit):
            return
        try:
            d_limit = Decimal(str(credit_limit))
        except Exception:
            return
        if d_limit <= Decimal("0.00"):
            return

        stmt_bal = text("""
            SELECT (
                c.opening_credit
                + COALESCE((SELECT SUM(total) FROM sales WHERE client_id = c.id AND sale_type = 'credit'), 0)
                + COALESCE((SELECT SUM(total) FROM raw_sales WHERE client_id = c.id AND sale_type = 'credit'), 0)
                - COALESCE((SELECT SUM(amount) FROM payments WHERE client_id = c.id AND payment_type IN ('versement', 'avance')), 0)
            ) AS balance
            FROM clients c WHERE c.id = :cid
        """)
        res_bal = await session.execute(stmt_bal, {"cid": client_id})
        scalar_val = res_bal.scalar() if hasattr(res_bal, "scalar") else None
        if inspect.isawaitable(scalar_val):
            scalar_val = await scalar_val
        curr_bal = Decimal(str(scalar_val or "0.00"))
        projected = curr_bal + additional_debt

        if projected > d_limit:
            c_name = getattr(client, "name", f"Client #{client_id}")
            raise ValidationError(
                f"Plafond de crédit dépassé pour {c_name} : encours actuel ({curr_bal:,.2f} DA) + "
                f"nouvelle créance ({additional_debt:,.2f} DA) = {projected:,.2f} DA "
                f"(plafond autorisé : {d_limit:,.2f} DA)."
            )

    @staticmethod
    def validate_sale_type(client_id: int | None, sale_type: str) -> None:
        if sale_type.strip().lower() == "credit" and not client_id:
            raise ValidationError("Une vente à crédit nécessite un client.")

    @staticmethod
    def validate_quantity(qty: float) -> None:
        if math.isnan(qty) or math.isinf(qty) or qty <= 0:
            raise ValidationError("La quantité doit être un nombre strictement positif et fini.")
        if qty > 1e9:
            raise ValidationError("La quantité dépasse la limite autorisée.")

    @staticmethod
    async def validate_stock_availability(
        item_kind: str, item_id: int, qty: float, unit: str, custom_item_name: str, session: AsyncSession
    ) -> tuple[FinishedProduct | RawMaterial, float]:
        qty_kg = float(qty_to_kg(qty, unit))

        if item_kind in {"finished", "sale_finished"}:
            stmt = select(FinishedProduct).where(FinishedProduct.id == item_id).with_for_update()
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                raise NotFoundError("Produit fini", item_id)

            stock_before = float(item.stock_qty)
            if qty_kg > stock_before:
                raise ValidationError(
                    f"Stock produit insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg)."
                )
            return item, qty_kg

        elif item_kind in {"raw", "sale_raw"}:
            stmt = select(RawMaterial).where(RawMaterial.id == item_id).with_for_update()
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                raise NotFoundError("Matière première", item_id)

            custom_item_name = custom_item_name.strip()
            is_other = str(item.name or "").strip().casefold() == "autre"
            if is_other and not custom_item_name:
                raise ValidationError("Précise le nom du produit pour la ligne AUTRE.")

            stock_before = float(item.stock_qty)
            if qty_kg > stock_before:
                raise ValidationError(
                    f"Stock matière insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg)."
                )
            return item, qty_kg
        else:
            raise ValidationError(f"Type d'article inconnu : {item_kind}")
