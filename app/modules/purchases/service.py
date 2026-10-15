from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text

from app.core.events import DomainEvent, emit
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.models import (
    FinishedProduct,
    Purchase,
    PurchaseDocument,
    RawMaterial,
    StockMovement,
    Supplier,
    SupplierPayment,
)
from app.infra.document_numbering import next_doc_number
from app.infra.perf_cache import invalidate_cache_domains
from app.modules.catalog.stock_service import qty_to_kg, unit_choices, unit_price_to_kg
from app.modules.purchases.repository import PurchaseDocumentRepository, PurchaseRepository
from app.modules.purchases.schemas import PurchaseFormSchema


class PurchaseService:
    """Asynchronous business service layer for the Purchases module."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.purchase_repo = PurchaseRepository(session)
        self.doc_repo = PurchaseDocumentRepository(session)

    async def list_purchases(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.purchase_repo.list_purchases_paginated(
            search=search,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    async def purchase_form_context(self) -> dict:
        raw_choices = await self.purchase_repo.list_raw_material_choices()
        # Fetch suppliers
        stmt = select(Supplier).order_by(Supplier.name)
        res = await self.session.execute(stmt)
        suppliers = [dict(s._mapping) for s in res.fetchall()]
        return {"suppliers": suppliers, "raw_materials": raw_choices, "units": unit_choices()}

    async def get_purchase_document_context(self, document_id: int) -> Optional[dict]:
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            return None
        lines = await self.doc_repo.list_lines(document_id)
        return {
            "purchase_document": document,
            "purchase_lines": lines,
        }

    async def get_purchase_edit_context(self, purchase_id: int) -> Optional[dict]:
        purchase = await self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            return None
        if purchase.get("document_id"):
            context = await self.get_purchase_document_context(int(purchase["document_id"]))
            if context:
                context["redirect_document_id"] = int(purchase["document_id"])
            return context

        return {
            "purchase_document": {
                "id": None,
                "supplier_id": purchase.get("supplier_id"),
                "purchase_date": purchase.get("purchase_date"),
                "notes": purchase.get("notes") or "",
            },
            "purchase_lines": [purchase],
        }

    async def create_purchase_record(
        self,
        supplier_id: int | None,
        item_kind: str,
        item_id: int,
        qty: float | Decimal,
        unit: str,
        unit_price: float | Decimal,
        purchase_date: date,
        notes: str,
        document_id: int | None = None,
        custom_item_name: str = "",
    ) -> int:
        d_qty = Decimal(str(qty))
        d_unit_price = Decimal(str(unit_price))
        if d_qty <= Decimal("0"):
            raise ValidationError("La quantité doit être supérieure à zéro.")
        if d_unit_price <= Decimal("0"):
            raise ValidationError("Le prix unitaire doit être supérieur à zéro.")

        custom_item_name = custom_item_name.strip()
        total = d_qty * d_unit_price
        qty_kg = qty_to_kg(d_qty, unit)
        unit_price_kg = unit_price_to_kg(d_unit_price, unit)

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
                quantity=d_qty,
                unit=unit,
                unit_price=d_unit_price,
                total=total,
                purchase_date=purchase_date,
                notes=notes,
                custom_item_name=custom_item_name,
            )
            self.session.add(purchase_row)
            await self.session.flush()
            purchase_id = purchase_row.id

            stock_before = Decimal(str(item.stock_qty))
            stock_after = stock_before + qty_kg
            if stock_before <= Decimal("0"):
                avg_cost = unit_price_kg
            else:
                current_value = stock_before * Decimal(str(item.avg_cost))
                added_value = qty_kg * unit_price_kg
                total_stock = stock_before + qty_kg
                avg_cost = (current_value + added_value) / total_stock if total_stock > Decimal("0") else unit_price_kg
            sale_price = Decimal(str(item.sale_price)) if item.sale_price else d_unit_price

            item.stock_qty = stock_after
            item.avg_cost = avg_cost
            item.sale_price = sale_price
            self.session.add(item)

            await self.record_stock_movement(
                "raw",
                item_id,
                "in",
                qty_kg,
                "kg",
                stock_before,
                stock_after,
                "create_purchase",
                "purchase",
                purchase_id,
            )
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
                quantity=d_qty,
                unit=unit,
                unit_price=d_unit_price,
                total=total,
                purchase_date=purchase_date,
                notes=notes,
                custom_item_name=custom_item_name,
            )
            self.session.add(purchase_row)
            await self.session.flush()
            purchase_id = purchase_row.id

            stock_before = Decimal(str(item.stock_qty))
            stock_after = stock_before + qty_kg
            if stock_before <= Decimal("0"):
                avg_cost = unit_price_kg
            else:
                current_value = stock_before * Decimal(str(item.avg_cost))
                added_value = qty_kg * unit_price_kg
                total_stock = stock_before + qty_kg
                avg_cost = (current_value + added_value) / total_stock if total_stock > Decimal("0") else unit_price_kg
            sale_price = Decimal(str(item.sale_price)) if item.sale_price else d_unit_price

            item.stock_qty = stock_after
            item.avg_cost = avg_cost
            item.sale_price = sale_price
            self.session.add(item)

            await self.record_stock_movement(
                "finished",
                item_id,
                "in",
                qty_kg,
                "kg",
                stock_before,
                stock_after,
                "create_purchase",
                "purchase",
                purchase_id,
            )

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
            qty_kg = qty_to_kg(Decimal(str(row.quantity)), row.unit)
            if not product or Decimal(str(product.stock_qty)) < qty_kg:
                return False

            stock_before = Decimal(str(product.stock_qty))
            stock_after = stock_before - qty_kg

            current_value = stock_before * Decimal(str(product.avg_cost))
            removed_value = Decimal(str(row.total))
            restored_value = current_value - removed_value
            avg_cost_restored = max(Decimal("0.00"), restored_value / stock_after) if stock_after > Decimal("0") else Decimal(str(product.avg_cost))

            product.stock_qty = stock_after
            product.avg_cost = avg_cost_restored
            self.session.add(product)
            await self.session.delete(row)
            await self.session.flush()

            await self.record_stock_movement(
                "finished",
                int(row.finished_product_id),
                "out",
                qty_kg,
                "kg",
                stock_before,
                stock_after,
                "reverse_purchase",
                "purchase",
                purchase_id,
            )
        else:
            stmt_mat = select(RawMaterial).where(RawMaterial.id == row.raw_material_id).with_for_update()
            res_mat = await self.session.execute(stmt_mat)
            material = res_mat.scalar_one_or_none()
            qty_kg = qty_to_kg(Decimal(str(row.quantity)), row.unit)
            if not material or Decimal(str(material.stock_qty)) < qty_kg:
                return False

            stock_before = Decimal(str(material.stock_qty))
            stock_after = stock_before - qty_kg

            current_value = stock_before * Decimal(str(material.avg_cost))
            removed_value = Decimal(str(row.total))
            restored_value = current_value - removed_value
            avg_cost_restored = max(Decimal("0.00"), restored_value / stock_after) if stock_after > Decimal("0") else Decimal(str(material.avg_cost))

            material.stock_qty = stock_after
            material.avg_cost = avg_cost_restored
            self.session.add(material)
            await self.session.delete(row)
            await self.session.flush()

            await self.record_stock_movement(
                "raw",
                int(row.raw_material_id),
                "out",
                qty_kg,
                "kg",
                stock_before,
                stock_after,
                "reverse_purchase",
                "purchase",
                purchase_id,
            )

        if recalc and row.document_id:
            await self.recalc_purchase_document_totals(int(row.document_id))
        return True

    async def record_stock_movement(
        self,
        item_kind: str,
        item_id: int,
        direction: str,
        quantity: float | Decimal,
        unit: str,
        stock_before: float | Decimal,
        stock_after: float | Decimal,
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
                quantity=Decimal(str(quantity)),
                unit=unit,
                stock_before=Decimal(str(stock_before)),
                stock_after=Decimal(str(stock_after)),
                reason=reason,
                reference_type=reference_type,
                reference_id=reference_id,
                created_by_username=username,
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
            {"doc_id": document_id},
        )
        first_row = res.first()
        stats = dict(first_row._mapping) if first_row else {"line_count": 0, "total_amount": 0}

        line_count = int(stats.get("line_count") or 0)
        if line_count <= 0:
            doc = await self.doc_repo.get(document_id)
            if doc:
                await self.session.delete(doc)
            return

        total = Decimal(str(stats["total_amount"] or 0))

        doc = await self.doc_repo.get(document_id)
        if doc:
            doc.total = total
            self.session.add(doc)

    async def _insert_purchase_document(self, supplier_id: int | None, purchase_date: date, notes: str) -> int:
        year = purchase_date.year
        doc_number = await asyncio.to_thread(next_doc_number, "BA", year)

        doc = PurchaseDocument(
            doc_number=doc_number, supplier_id=supplier_id, total=Decimal("0.00"), purchase_date=purchase_date, notes=notes
        )
        self.session.add(doc)
        await self.session.flush()
        return doc.id

    async def create_purchase_from_form(self, schema: PurchaseFormSchema) -> dict:
        supplier_id = schema.supplier_id
        purchase_date = schema.purchase_date
        notes = schema.notes
        lines = schema.lines
        if not lines:
            raise ValidationError("Le bon d'achat doit contenir au moins une ligne d'article.")

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
                    after=created,
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
        emit(DomainEvent("create", "purchase_document", doc_id, f"{len(lines)} ligne(s)", after=created))

        return {
            "mode": "document",
            "document_id": doc_id,
            "print_doc_type": "purchase_document",
            "print_item_id": doc_id,
            "line_count": len(lines),
            "first_purchase_id": created_ids[0],
        }

    async def edit_purchase_document_from_form(self, document_id: int, schema: PurchaseFormSchema) -> dict:
        context = await self.get_purchase_document_context(document_id)
        if not context:
            raise NotFoundError("Bon d'achat", document_id)

        supplier_id = schema.supplier_id
        purchase_date = schema.purchase_date
        notes = schema.notes
        lines = schema.lines
        if not lines:
            raise ValidationError("Le bon d'achat doit contenir au moins une ligne d'article.")

        before = {
            "document": context["purchase_document"],
            "lines": context["purchase_lines"],
        }

        # Reverse previous lines without deleting parent document
        for line in context["purchase_lines"]:
            if not await self.reverse_purchase(int(line["row_id"]), recalc=False):
                raise ValueError("Impossible de modifier cet achat car le stock ne permet pas de l'annuler.")

        # Update document header attributes
        doc = await self.doc_repo.get(document_id)
        if doc:
            doc.supplier_id = supplier_id
            doc.purchase_date = purchase_date
            doc.notes = notes
            self.session.add(doc)

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

        await self.session.commit()

        after_context = await self.get_purchase_document_context(document_id)
        invalidate_cache_domains("purchases", "catalog", "supplier", "dashboard")
        emit(
            DomainEvent(
                "update", "purchase_document", document_id, f"{len(lines)} ligne(s)", before=before, after=after_context
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
                    "update", "purchase_document", document_id, f"{len(lines)} ligne(s)", before=before, after=created
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
                after=latest,
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
            emit(DomainEvent("delete", "purchase", purchase_id, "Suppression achat", before=before, after=None))
        return ok

    @staticmethod
    async def create_supplier_payment(
        supplier_id: int,
        amount: Any,
        payment_type: str = "versement",
        notes: str = "",
        purchase_id: int | None = None,
        payment_date: str | None = None,
        db: AsyncSession | None = None,
    ) -> int:
        return await create_supplier_payment(
            supplier_id=supplier_id,
            amount=amount,
            payment_type=payment_type,
            notes=notes,
            purchase_id=purchase_id,
            payment_date=payment_date,
            db=db,
        )



async def create_supplier_payment(
    supplier_id: int,
    amount: Any,
    payment_type: str = "versement",
    notes: str = "",
    purchase_id: int | None = None,
    payment_date: str | None = None,
    db: AsyncSession | None = None,
) -> int:
    """Enregistre un paiement/versement fournisseur via le Unit of Work."""
    from datetime import date
    from decimal import Decimal

    from app.core.exceptions import NotFoundError, ValidationError
    from app.core.uow import unit_of_work

    amt = Decimal(str(amount or 0))
    if amt <= Decimal("0"):
        raise ValidationError("Le montant du versement doit être supérieur à 0.")

    if payment_date:
        p_date_obj = date.fromisoformat(str(payment_date)) if isinstance(payment_date, str) else payment_date
    else:
        p_date_obj = date.today()
    async with unit_of_work(db) as session:
        supplier_exists = (
            await session.execute(select(Supplier.id).where(Supplier.id == supplier_id).with_for_update())
        ).fetchone()
        if not supplier_exists:
            raise NotFoundError("Fournisseur", supplier_id)

        sp = SupplierPayment(
            supplier_id=supplier_id,
            purchase_id=purchase_id,
            payment_type=payment_type,
            amount=amt,
            payment_date=p_date_obj,
            notes=notes,
        )
        session.add(sp)
        await session.flush()
        if sp.id is not None:
            return sp.id

        # Fallback pour sessions mockées en tests unitaires sans moteur d'autoincrément ORM
        if hasattr(session, "execute"):
            try:
                res = await session.execute(
                    select(SupplierPayment.id)
                    .where(SupplierPayment.supplier_id == supplier_id)
                    .order_by(SupplierPayment.id.desc())
                    .limit(1)
                )
                row = res.fetchone() if hasattr(res, "fetchone") else None
                if row and row[0] is not None:
                    return int(row[0])
            except Exception:
                pass

        return 0
