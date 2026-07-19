from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.exceptions import ValidationError, NotFoundError
from app.core.models import Client, FinishedProduct, RawMaterial
from app.services.stock_service import qty_to_kg

class SalesValidator:
    """Valide les règles métier du module Sales."""

    @staticmethod
    async def validate_client(client_id: int | None, session: AsyncSession) -> None:
        if client_id:
            client = await session.get(Client, client_id)
            if not client:
                raise NotFoundError("Client", client_id)

    @staticmethod
    def validate_sale_type(client_id: int | None, sale_type: str) -> None:
        if sale_type.strip().lower() == "credit" and not client_id:
            raise ValidationError("Une vente à crédit nécessite un client.")

    @staticmethod
    def validate_quantity(qty: float) -> None:
        if qty <= 0:
            raise ValidationError("La quantité doit être supérieure à zéro.")

    @staticmethod
    async def validate_stock_availability(
        item_kind: str,
        item_id: int,
        qty: float,
        unit: str,
        custom_item_name: str,
        session: AsyncSession
    ) -> tuple[FinishedProduct | RawMaterial, float]:
        qty_kg = qty_to_kg(qty, unit)

        if item_kind == "finished" or item_kind == "sale_finished":
            # Fetch finished product
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

        elif item_kind == "raw" or item_kind == "sale_raw":
            # Fetch raw material
            stmt = select(RawMaterial).where(RawMaterial.id == item_id).with_for_update()
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                raise NotFoundError("Matière première", item_id)

            custom_item_name = custom_item_name.strip()
            is_other = str(item.name or "").strip().casefold() == "autre"
            if is_other:
                if not custom_item_name:
                    raise ValidationError("Précise le nom du produit pour la ligne AUTRE.")

            stock_before = float(item.stock_qty)
            if qty_kg > stock_before:
                raise ValidationError(
                    f"Stock matière insuffisant (disponible: {stock_before:.2f} kg, requis: {qty_kg:.2f} kg)."
                )
            return item, qty_kg
        else:
            raise ValidationError(f"Type d'article inconnu : {item_kind}")
