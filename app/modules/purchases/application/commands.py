from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, emit
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.services.stock_service import qty_to_kg, unit_price_to_kg
from app.core.document_numbering import next_doc_number
from app.core.perf_cache import invalidate_cache_domains
from app.core.models import Purchase, PurchaseDocument, StockMovement, FinishedProduct, RawMaterial
from app.modules.purchases.infrastructure.repository import PurchaseRepository, PurchaseDocumentRepository
from app.modules.purchases.api.schemas import PurchaseFormSchema
from app.modules.purchases.application.queries import PurchaseQueries


class PurchaseCommands:
    """Gestion des commandes (Commands / écritures) du module Achats."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.purchase_repo = PurchaseRepository(session)
        self.doc_repo = PurchaseDocumentRepository(session)
        self.queries = PurchaseQueries(session)

    async def create_purchase_record(
        self,
        supplier_id: int | None,
        item_kind: str,
        item_id: int,
        qty: float,
        unit: str,
        unit_price: float,
        purchase_date: date,
        notes: str,
        document_id: int | None = None,
        custom_item_name: str = "",
    ) -> int:
        if qty <= 0:
            raise ValidationError("La quantité doit être supérieure à zéro.")
        if unit_price <= 0:
            raise ValidationError("Le prix unitaire doit être supérieur à zéro.")

        custom_item_name = custom_item_name.strip()
        total = qty * unit_price
        qty_kg = qty_to_kg(qty, unit)
        unit_price_kg = unit_price_to_kg(unit_price, unit)

        if item_kind == "raw":
            stmt = select(RawMaterial).where(RawMaterial.id == item_id).with_for_update()
            res = await self.session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                raise NotFoundError("Matière première", item_id)

            is_other = str(item.name or "").strip().casefold() == "autre"
            if is_other:
                unit = "unite"
                if not custom_item_name:
                    raise ValidationError("Précise le nom du produit pour la ligne AUTRE.")
            else:
                custom_item_name = ""

            purchase_row = Purchase(
                supplier_id=supplier_id,
                document_id=document_id,
                raw_material_id=item_id,
                finished_product_id=None,
                quantity=qty_kg,
                unit=unit,
                unit_price=unit_price_kg,
                total=total,
                purchase_date=purchase_date,
                notes=notes,
                custom_item_name=custom_item_name
            )
            self.session.add(purchase_row)
            await self.session.flush()
            purchase_id = purchase_row.id

            stock_before = float(item.stock_qty)
            stock_after = stock_before + qty_kg
            current_value = stock_before * float(item.avg_cost)
            added_value = qty_kg * unit_price_kg
            avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0.0
            sale_price = float(item.sale_price) or unit_price

            item.stock_qty = stock_after
            item.avg_cost = avg_cost
            item.sale_price = sale_price
            self.session.add(item)

            await self.record_stock_movement("raw", item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id)
        else:
            stmt = select(FinishedProduct).where(FinishedProduct.id == item_id).with_for_update()
            res = await self.session.execute(stmt)
            item = res.scalar_one_or_none()
            if not item:
                raise NotFoundError("Produit fini", item_id)

            purchase_row = Purchase(
                supplier_id=supplier_id,
                document_id=document_id,
                raw_material_id=None,
                finished_product_id=item_id,
                quantity=qty_kg,
                unit=unit,
                unit_price=unit_price_kg,
                total=total,
                purchase_date=purchase_date,
                notes=notes,
                custom_item_name=custom_item_name
            )
            self.session.add(purchase_row)
            await self.session.flush()
            purchase_id = purchase_row.id

            stock_before = float(item.stock_qty)
            stock_after = stock_before + qty_kg
            current_value = stock_before * float(item.avg_cost)
            added_value = qty_kg * unit_price_kg
            avg_cost = (current_value + added_value) / stock_after if stock_after > 0 else 0.0
            sale_price = float(item.sale_price) or unit_price

            item.stock_qty = stock_after
            item.avg_cost = avg_cost
            item.sale_price = sale_price
            self.session.add(item)

            await self.record_stock_movement("finished", item_id, "in", qty_kg, "kg", stock_before, stock_after, "create_purchase", "purchase", purchase_id)

        await self.recalc_purchase_document_totals(document_id)
        return purchase_id

    async def reverse_purchase(self, purchase_id: int, recalc: bool = True) -> bool:
        stmt_purchase = select(Purchase).where(Purchase.id == purchase_id)
        res_p = await self.session.execute(stmt_purchase)
        row = res_p.scalar_one_or_none()
        if not row:
            return False

        if row.finished_product_id:
            stmt_prod = select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id).with_for_update()
            res_prod = await self.session.execute(stmt_prod)
            product = res_prod.scalar_one_or_none()
            if not product or float(product.stock_qty) < float(row.quantity):
                return False

            stock_before = float(product.stock_qty)
            stock_after = stock_before - float(row.quantity)

            current_value = stock_before * float(product.avg_cost)
            removed_value = float(row.quantity) * float(row.unit_price)
            restored_value = current_value - removed_value
            avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(product.avg_cost)

            product.stock_qty = stock_after
            product.avg_cost = avg_cost_restored
            self.session.add(product)
            await self.session.delete(row)
            await self.session.flush()

            await self.record_stock_movement("finished", int(row.finished_product_id), "out", float(row.quantity), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id)
        else:
            stmt_mat = select(RawMaterial).where(RawMaterial.id == row.raw_material_id).with_for_update()
            res_mat = await self.session.execute(stmt_mat)
            material = res_mat.scalar_one_or_none()
            if not material or float(material.stock_qty) < float(row.quantity):
                return False

            stock_before = float(material.stock_qty)
            stock_after = stock_before - float(row.quantity)

            current_value = stock_before * float(material.avg_cost)
            removed_value = float(row.quantity) * float(row.unit_price)
            restored_value = current_value - removed_value
            avg_cost_restored = restored_value / stock_after if stock_after > 0 else float(material.avg_cost)

            material.stock_qty = stock_after
            material.avg_cost = avg_cost_restored
            self.session.add(material)
            await self.session.delete(row)
            await self.session.flush()

            await self.record_stock_movement("raw", int(row.raw_material_id), "out", float(row.quantity), "kg", stock_before, stock_after, "reverse_purchase", "purchase", purchase_id)

        if recalc and row.document_id:
            await self.recalc_purchase_document_totals(int(row.document_id))
        return True

    async def record_stock_movement(
        self,
        item_kind: str,
        item_id: int,
        direction: str,
        quantity: float,
        unit: str,
        stock_before: float,
        stock_after: float,
        reason: str,
        reference_type: str,
        reference_id: int | None,
    ) -> None:
        try:
            from app.core.request_state import get_state_value
            actor = get_state_value("user")
            username = actor["username"] if actor else "system"

            movement = StockMovement(
                item_kind=item_kind,
                item_id=item_id,
                direction=direction,
                quantity=quantity,
                unit=unit,
                stock_before=stock_before,
                stock_after=stock_after,
                reason=reason,
                reference_type=reference_type,
                reference_id=reference_id,
                created_by_username=username
            )
            self.session.add(movement)
        except Exception:
            pass

    async def recalc_purchase_document_totals(self, document_id: int | None) -> None:
        if not document_id:
            return

        res = await self.session.execute(
            text("""
                SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount
                FROM purchases WHERE document_id = :doc_id
            """),
            {"doc_id": document_id}
        )
        stats = dict(res.first()._mapping)

        line_count = int(stats["line_count"] or 0)
        if line_count <= 0:
            doc = await self.doc_repo.get(document_id)
            if doc:
                await self.session.delete(doc)
            return

        total = float(stats["total_amount"] or 0)

        doc = await self.doc_repo.get(document_id)
        if doc:
            doc.total = total
            self.session.add(doc)

    async def _insert_purchase_document(
        self,
        supplier_id: int | None,
        purchase_date: date,
        notes: str
    ) -> int:
        year = purchase_date.year
        doc_number = await asyncio.to_thread(next_doc_number, "BA", year)

        doc = PurchaseDocument(
            doc_number=doc_number,
            supplier_id=supplier_id,
            total=0.0,
            purchase_date=purchase_date,
            notes=notes
        )
        self.session.add(doc)
        await self.session.flush()
        return doc.id

    async def create_purchase_from_form(self, schema: PurchaseFormSchema) -> dict:
        supplier_id = schema.supplier_id
        purchase_date = schema.purchase_date
        notes = schema.notes
        lines = schema.lines

        use_document = len(lines) > 1

        if not use_document:
            line = lines[0]
            parts = line.raw_material_id.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            created_purchase_id = await self.create_purchase_record(
                supplier_id,
                item_kind,
                item_id,
                line.quantity,
                line.unit,
                line.unit_price,
                purchase_date,
                notes,
                custom_item_name=line.custom_item_name,
            )
            await self.session.commit()

            created = await self.purchase_repo.get_by_id(created_purchase_id)
            invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
            emit(
                DomainEvent(
                    "create",
                    "purchase",
                    created_purchase_id,
                    f"{item_kind} #{item_id} qty={line.quantity} {line.unit}",
                    after=created
                )
            )

            return {
                "mode": "line",
                "document_id": None,
                "print_doc_type": "purchase",
                "print_item_id": created_purchase_id,
                "line_count": 1,
                "first_purchase_id": created_purchase_id,
            }

        # Create multi-line document
        doc_id = await self._insert_purchase_document(supplier_id, purchase_date, notes)
        created_ids: list[int] = []
        for line in lines:
            parts = line.raw_material_id.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            created_ids.append(
                await self.create_purchase_record(
                    supplier_id,
                    item_kind,
                    item_id,
                    line.quantity,
                    line.unit,
                    line.unit_price,
                    purchase_date,
                    notes,
                    document_id=doc_id,
                    custom_item_name=line.custom_item_name,
                )
            )

        await self.session.commit()

        created = await self.doc_repo.get_by_id(doc_id)
        invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
        emit(
            DomainEvent(
                "create",
                "purchase_document",
                doc_id,
                f"{len(lines)} ligne(s)",
                after=created
            )
        )

        return {
            "mode": "document",
            "document_id": doc_id,
            "print_doc_type": "purchase_document",
            "print_item_id": doc_id,
            "line_count": len(lines),
            "first_purchase_id": created_ids[0],
        }

    async def edit_purchase_document_from_form(self, document_id: int, schema: PurchaseFormSchema) -> dict:
        context = await self.queries.get_purchase_document_context(document_id)
        if not context:
            raise NotFoundError("Bon d'achat", document_id)

        supplier_id = schema.supplier_id
        purchase_date = schema.purchase_date
        notes = schema.notes
        lines = schema.lines

        before = {
            "document": context["purchase_document"],
            "lines": context["purchase_lines"],
        }

        # Reverse previous lines
        for line in context["purchase_lines"]:
            if not await self.reverse_purchase(int(line["row_id"])):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")

        # Re-insert document if deleted during reverse
        doc = await self.doc_repo.get(document_id)
        if not doc:
            await self._insert_purchase_document(supplier_id, purchase_date, notes)

        # Insert new lines
        created_ids: list[int] = []
        for line in lines:
            parts = line.raw_material_id.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            created_ids.append(
                await self.create_purchase_record(
                    supplier_id,
                    item_kind,
                    item_id,
                    line.quantity,
                    line.unit,
                    line.unit_price,
                    purchase_date,
                    notes,
                    document_id=document_id,
                    custom_item_name=line.custom_item_name,
                )
            )

        # Update document header
        doc = await self.doc_repo.get(document_id)
        if doc:
            doc.supplier_id = supplier_id
            doc.purchase_date = purchase_date
            doc.notes = notes
            self.session.add(doc)

        await self.session.commit()

        after_context = await self.queries.get_purchase_document_context(document_id)
        invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
        emit(
            DomainEvent(
                "update",
                "purchase_document",
                document_id,
                f"{len(lines)} ligne(s)",
                before=before,
                after=after_context
            )
        )

        return {
            "mode": "document",
            "document_id": document_id,
            "print_doc_type": "purchase_document",
            "print_item_id": document_id,
            "line_count": len(lines),
            "first_purchase_id": created_ids[0],
        }

    async def edit_purchase_from_form(self, purchase_id: int, schema: PurchaseFormSchema) -> dict:
        before = await self.purchase_repo.get_by_id(purchase_id)
        if not before:
            raise NotFoundError("Achat", purchase_id)
        if before.get("document_id"):
            raise ConflictError("Cette ligne appartient déjà à un bon multi-lignes.")

        supplier_id = schema.supplier_id
        purchase_date = schema.purchase_date
        notes = schema.notes
        lines = schema.lines

        if len(lines) > 1:
            # Promote to multi-line
            if not await self.reverse_purchase(purchase_id):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")

            document_id = await self._insert_purchase_document(supplier_id, purchase_date, notes)
            created_ids: list[int] = []
            for line in lines:
                parts = line.raw_material_id.split(":")
                item_kind = parts[0]
                item_id = int(parts[1])

                created_ids.append(
                    await self.create_purchase_record(
                        supplier_id,
                        item_kind,
                        item_id,
                        line.quantity,
                        line.unit,
                        line.unit_price,
                        purchase_date,
                        notes,
                        document_id=document_id,
                        custom_item_name=line.custom_item_name,
                    )
                )

            await self.session.commit()

            created = await self.doc_repo.get_by_id(document_id)
            invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
            emit(
                DomainEvent(
                    "update",
                    "purchase_document",
                    document_id,
                    f"{len(lines)} ligne(s)",
                    before=before,
                    after=created
                )
            )

            return {
                "mode": "document",
                "document_id": document_id,
                "print_doc_type": "purchase_document",
                "print_item_id": document_id,
                "line_count": len(lines),
                "first_purchase_id": created_ids[0],
            }

        # Keep as single line purchase
        line = lines[0]
        parts = line.raw_material_id.split(":")
        item_kind = parts[0]
        item_id = int(parts[1])

        if not await self.reverse_purchase(purchase_id):
            raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")

        new_purchase_id = await self.create_purchase_record(
            supplier_id,
            item_kind,
            item_id,
            line.quantity,
            line.unit,
            line.unit_price,
            purchase_date,
            notes,
            custom_item_name=line.custom_item_name,
        )

        await self.session.commit()

        latest = await self.purchase_repo.get_by_id(new_purchase_id)
        invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
        emit(
            DomainEvent(
                "update",
                "purchase",
                purchase_id,
                f"{line.raw_material_id} #{item_id} qty={line.quantity} {line.unit}",
                before=before,
                after=latest
            )
        )

        return {
            "mode": "line",
            "document_id": None,
            "print_doc_type": "purchase",
            "print_item_id": new_purchase_id,
            "line_count": 1,
            "first_purchase_id": new_purchase_id,
        }

    async def delete_purchase_by_id(self, purchase_id: int) -> bool:
        before = await self.purchase_repo.get_by_id(purchase_id)
        if not before:
            return False

        ok = await self.reverse_purchase(purchase_id)
        if ok:
            await self.session.commit()
            invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
            emit(
                DomainEvent(
                    "delete",
                    "purchase",
                    purchase_id,
                    "Suppression achat",
                    before=before,
                    after=None
                )
            )
        return ok
