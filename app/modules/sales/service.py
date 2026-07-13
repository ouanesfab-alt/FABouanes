from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, emit
from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.core.helpers import unit_choices
from app.core.request_state import get_state_value
from app.services.stock_service import qty_to_kg
from app.core.document_numbering import next_doc_number
from app.core.perf_cache import invalidate_cache_domains
from app.core.models import Sale, RawSale, SaleDocument, StockMovement, Payment, FinishedProduct, RawMaterial
from app.modules.sales.repository import SaleRepository, RawSaleRepository, SaleDocumentRepository
from app.modules.sales.schemas_validation import SaleFormSchema


class SalesService:
    """Asynchronous business service layer for the Sales module."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.sale_repo = SaleRepository(session)
        self.raw_sale_repo = RawSaleRepository(session)
        self.doc_repo = SaleDocumentRepository(session)

    async def list_sales(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        return await self.sale_repo.list_sales_paginated(
            search=search,
            date_from=date_from,
            date_to=date_to,
            kind=kind,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def sale_form_context(self) -> dict:
        sellable = await self.sale_repo.list_sellable_items()
        return {"sellable_items": sellable, "units": unit_choices()}

    async def get_sale_document_context(self, document_id: int) -> Optional[dict]:
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            return None
        lines = await self.doc_repo.list_lines(document_id)
        refs = {(str(line["row_kind"]), int(line["row_id"])) for line in lines}
        has_linked = False
        if document.client_id and refs:
            has_linked = await self.doc_repo.document_has_linked_payments(document_id, int(document.client_id), refs)

        return {
            "sale_document": document.model_dump(),
            "sale_lines": lines,
            "has_linked_payments": has_linked,
        }

    async def get_sale_edit_context(self, kind: str, row_id: int) -> Optional[dict]:
        sale = await self.sale_repo.get_sale_detail(kind, row_id)
        if not sale:
            return None
        if sale.get("document_id"):
            context = await self.get_sale_document_context(int(sale["document_id"]))
            if context:
                context["redirect_document_id"] = int(sale["document_id"])
            return context

        return {
            "sale_document": {
                "id": None,
                "client_id": sale.get("client_id"),
                "sale_type": sale.get("sale_type"),
                "sale_date": sale.get("sale_date"),
                "notes": sale.get("notes") or "",
            },
            "sale_lines": [
                {
                    "row_id": int(sale["id"]),
                    "document_id": None,
                    "row_kind": str(sale["row_kind"]),
                    "item_key": str(sale["item_key"]),
                    "item_name": str(sale["item_name"]),
                    "item_kind": "Produit final" if sale["row_kind"] == "finished" else "Matière première",
                    "quantity": float(sale["quantity"]),
                    "unit": str(sale["unit"]),
                    "unit_price": float(sale["unit_price"]),
                    "total": float(sale["total"]),
                    "amount_paid": float(sale["amount_paid"]),
                    "balance_due": float(sale["balance_due"]),
                    "custom_item_name": str(sale["custom_item_name"] or ""),
                }
            ],
            "has_linked_payments": False,
        }

    async def create_sale_record(
        self,
        client_id: int | None,
        item_kind: str,
        item_id: int,
        qty: float,
        unit: str,
        unit_price: float,
        sale_type: str,
        sale_date: date,
        notes: str,
        amount_paid_input: float = 0.0,
        document_id: int | None = None,
        custom_item_name: str = "",
    ) -> Tuple[str, int]:
        total = qty * unit_price
        requested_sale_type = sale_type.strip().lower()
        if requested_sale_type not in {"cash", "credit"}:
            requested_sale_type = "credit" if client_id else "cash"

        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_sale_type(client_id, requested_sale_type)
        SalesValidator.validate_quantity(qty)

        amount_paid = total if requested_sale_type == "cash" else max(0.0, min(amount_paid_input, total))
        balance_due = round(total - amount_paid, 2)

        if item_kind == "finished":
            item, qty_kg = await SalesValidator.validate_stock_availability(
                "finished", item_id, qty, unit, "", self.session
            )
            stock_before = float(item.stock_qty)
            cost_snapshot = float(item.avg_cost)
            profit_amount = total - qty_kg * cost_snapshot

            sale_row = Sale(
                client_id=client_id,
                document_id=document_id,
                finished_product_id=item_id,
                quantity=qty,
                unit=unit,
                unit_price=unit_price,
                total=total,
                sale_type=requested_sale_type,
                amount_paid=amount_paid,
                balance_due=balance_due,
                cost_price_snapshot=cost_snapshot,
                profit_amount=profit_amount,
                sale_date=sale_date,
                notes=notes
            )
            self.session.add(sale_row)
            await self.session.flush()
            row_id = sale_row.id

            stock_after = stock_before - qty_kg
            item.stock_qty = stock_after
            self.session.add(item)

            await self.record_stock_movement("finished", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "sale", row_id)

            if amount_paid > 0 and client_id:
                p_row = Payment(
                    client_id=client_id,
                    sale_id=row_id,
                    sale_kind="finished",
                    payment_type="versement",
                    amount=amount_paid,
                    payment_date=sale_date,
                    notes="Paiement initial vente"
                )
                self.session.add(p_row)

            await self.recalc_sale_document_totals(document_id)
            return "finished", row_id

        # Raw material sale
        stmt = select(RawMaterial).where(RawMaterial.id == item_id)
        res = await self.session.execute(stmt)
        rm_temp = res.scalar_one_or_none()
        if rm_temp and str(rm_temp.name or "").strip().casefold() == "autre":
            unit = "unite"

        item, qty_kg = await SalesValidator.validate_stock_availability(
            "raw", item_id, qty, unit, custom_item_name, self.session
        )
        custom_item_name = custom_item_name.strip() if str(item.name or "").strip().casefold() == "autre" else ""
        stock_before = float(item.stock_qty)
        cost_snapshot = float(item.avg_cost)
        profit_amount = total - qty_kg * cost_snapshot

        raw_sale_row = RawSale(
            client_id=client_id,
            document_id=document_id,
            raw_material_id=item_id,
            quantity=qty,
            unit=unit,
            unit_price=unit_price,
            total=total,
            sale_type=requested_sale_type,
            amount_paid=amount_paid,
            balance_due=balance_due,
            cost_price_snapshot=cost_snapshot,
            profit_amount=profit_amount,
            sale_date=sale_date,
            notes=notes,
            custom_item_name=custom_item_name
        )
        self.session.add(raw_sale_row)
        await self.session.flush()
        row_id = raw_sale_row.id

        stock_after = stock_before - qty_kg
        item.stock_qty = stock_after
        self.session.add(item)

        await self.record_stock_movement("raw", item_id, "out", qty_kg, "kg", stock_before, stock_after, "create_sale", "raw_sale", row_id)

        if amount_paid > 0 and client_id:
            p_row = Payment(
                client_id=client_id,
                raw_sale_id=row_id,
                sale_kind="raw",
                payment_type="versement",
                amount=amount_paid,
                payment_date=sale_date,
                notes="Paiement initial vente"
            )
            self.session.add(p_row)

        await self.recalc_sale_document_totals(document_id)
        return "raw", row_id

    async def reverse_sale(self, kind: str, row_id: int, recalc: bool = True) -> bool:
        if kind == "finished":
            stmt_sale = select(Sale).where(Sale.id == row_id)
            res_sale = await self.session.execute(stmt_sale)
            row = res_sale.scalar_one_or_none()
            if not row:
                return False

            stmt_prod = select(FinishedProduct).where(FinishedProduct.id == row.finished_product_id).with_for_update()
            res_prod = await self.session.execute(stmt_prod)
            product = res_prod.scalar_one_or_none()

            stock_before = float(product.stock_qty if product else 0)
            restore_qty = qty_to_kg(float(row.quantity), row.unit)
            stock_after = stock_before + restore_qty

            if product:
                product.stock_qty = stock_after
                self.session.add(product)

            # Delete payments associated with this sale
            await self.session.execute(
                text("DELETE FROM payments WHERE sale_kind = 'finished' AND sale_id = :sale_id"),
                {"sale_id": row_id}
            )

            # Delete sale row
            await self.session.delete(row)
            await self.session.flush()

            await self.record_stock_movement("finished", int(row.finished_product_id), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "sale", row_id)
            if recalc and row.document_id:
                await self.recalc_sale_document_totals(int(row.document_id))
            return True

        # Raw material sale reversal
        stmt_sale = select(RawSale).where(RawSale.id == row_id)
        res_sale = await self.session.execute(stmt_sale)
        row = res_sale.scalar_one_or_none()
        if not row:
            return False

        stmt_mat = select(RawMaterial).where(RawMaterial.id == row.raw_material_id).with_for_update()
        res_mat = await self.session.execute(stmt_mat)
        material = res_mat.scalar_one_or_none()

        stock_before = float(material.stock_qty if material else 0)
        restore_qty = qty_to_kg(float(row.quantity), row.unit)
        stock_after = stock_before + restore_qty

        if material:
            material.stock_qty = stock_after
            self.session.add(material)

        # Delete payments associated
        await self.session.execute(
            text("DELETE FROM payments WHERE sale_kind = 'raw' AND raw_sale_id = :raw_sale_id"),
            {"raw_sale_id": row_id}
        )

        # Delete raw sale row
        await self.session.delete(row)
        await self.session.flush()

        await self.record_stock_movement("raw", int(row.raw_material_id), "in", restore_qty, "kg", stock_before, stock_after, "reverse_sale", "raw_sale", row_id)
        if recalc and row.document_id:
            await self.recalc_sale_document_totals(int(row.document_id))
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

    async def recalc_sale_document_totals(self, document_id: int | None) -> None:
        if not document_id:
            return

        res_f = await self.session.execute(
            text("""
                SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount,
                       COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount
                FROM sales WHERE document_id = :doc_id
            """),
            {"doc_id": document_id}
        )
        finished = dict(res_f.first()._mapping)

        res_r = await self.session.execute(
            text("""
                SELECT COUNT(*) AS line_count, COALESCE(SUM(total), 0) AS total_amount,
                       COALESCE(SUM(amount_paid), 0) AS paid_amount, COALESCE(SUM(balance_due), 0) AS due_amount
                FROM raw_sales WHERE document_id = :doc_id
            """),
            {"doc_id": document_id}
        )
        raw = dict(res_r.first()._mapping)

        line_count = int(finished["line_count"] or 0) + int(raw["line_count"] or 0)
        if line_count <= 0:
            doc = await self.doc_repo.get(document_id)
            if doc:
                await self.session.delete(doc)
            return

        total = float(finished["total_amount"] or 0) + float(raw["total_amount"] or 0)
        paid = float(finished["paid_amount"] or 0) + float(raw["paid_amount"] or 0)
        due = float(finished["due_amount"] or 0) + float(raw["due_amount"] or 0)

        doc = await self.doc_repo.get(document_id)
        if doc:
            doc.total = total
            doc.amount_paid = paid
            doc.balance_due = due
            self.session.add(doc)

    async def _insert_sale_document(
        self,
        client_id: int | None,
        sale_type: str,
        sale_date: date,
        notes: str
    ) -> int:
        year = sale_date.year
        doc_number = await asyncio.to_thread(next_doc_number, "BV", year)

        doc = SaleDocument(
            doc_number=doc_number,
            client_id=client_id,
            sale_type=sale_type,
            total=0.0,
            amount_paid=0.0,
            balance_due=0.0,
            sale_date=sale_date,
            notes=notes
        )
        self.session.add(doc)
        await self.session.flush()
        return doc.id

    async def create_sale_from_form(self, schema: SaleFormSchema) -> dict:
        client_id = schema.client_id
        from app.modules.sales.validation import SalesValidator
        await SalesValidator.validate_client(client_id, self.session)

        sale_date = schema.sale_date
        notes = schema.notes
        sale_type = "credit" if client_id else "cash"
        lines = schema.lines

        use_document = len(lines) > 1

        newly_unlocked = []

        if not use_document:
            line = lines[0]
            parts = line.item_key.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            # Begin transaction
            created_kind, created_sale_id = await self.create_sale_record(
                client_id,
                item_kind,
                item_id,
                line.quantity,
                line.unit,
                line.unit_price,
                sale_type,
                sale_date,
                notes,
                0.0 if client_id else line.quantity * line.unit_price,
                custom_item_name=line.custom_item_name,
            )



            await self.session.commit()

            created = await self.sale_repo.get_sale_detail(created_kind, created_sale_id)
            invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
            emit(
                DomainEvent(
                    "create",
                    "sale",
                    created_sale_id,
                    f"{item_kind} #{item_id} qty={line.quantity} {line.unit}",
                    after=created
                )
            )

            # Store unlocked badges in session if request is present
            request = get_state_value("request")
            if request and hasattr(request, "session") and newly_unlocked:
                request.session["unlocked_badges"] = newly_unlocked

            return {
                "mode": "line",
                "document_id": None,
                "print_doc_type": "sale_finished" if created_kind == "finished" else "sale_raw",
                "print_item_id": created_sale_id,
                "line_count": 1,
                "first_line_kind": created_kind,
                "first_line_id": created_sale_id,
                "unlocked_badges": newly_unlocked,
            }

        # Create multi-line document
        doc_id = await self._insert_sale_document(client_id, sale_type, sale_date, notes)
        created_lines: list[tuple[str, int]] = []
        for line in lines:
            parts = line.item_key.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            created_lines.append(
                await self.create_sale_record(
                    client_id,
                    item_kind,
                    item_id,
                    line.quantity,
                    line.unit,
                    line.unit_price,
                    sale_type,
                    sale_date,
                    notes,
                    0.0 if client_id else line.quantity * line.unit_price,
                    document_id=doc_id,
                    custom_item_name=line.custom_item_name,
                )
            )



        await self.session.commit()

        created = await self.doc_repo.get_by_id(doc_id)
        invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
        emit(
            DomainEvent(
                "create",
                "sale_document",
                doc_id,
                f"{len(lines)} ligne(s)",
                after=created.model_dump() if created else None
            )
        )

        # Store unlocked badges in session if request is present
        request = get_state_value("request")
        if request and hasattr(request, "session") and newly_unlocked:
            request.session["unlocked_badges"] = newly_unlocked

        return {
            "mode": "document",
            "document_id": doc_id,
            "print_doc_type": "sale_document",
            "print_item_id": doc_id,
            "line_count": len(lines),
            "first_line_kind": created_lines[0][0],
            "first_line_id": created_lines[0][1],
            "unlocked_badges": newly_unlocked,
        }

    async def edit_sale_document_from_form(self, document_id: int, schema: SaleFormSchema) -> dict:
        context = await self.get_sale_document_context(document_id)
        if not context:
            raise NotFoundError("Facture", document_id)
        if context["has_linked_payments"]:
            raise ConflictError("Cette facture est déjà liée à des versements.")

        client_id = schema.client_id
        from app.modules.sales.validation import SalesValidator
        await SalesValidator.validate_client(client_id, self.session)
        sale_date = schema.sale_date
        notes = schema.notes
        sale_type = "credit" if client_id else "cash"
        lines = schema.lines

        before = {
            "document": context["sale_document"],
            "lines": context["sale_lines"],
        }

        # Reverse previous lines
        for line in context["sale_lines"]:
            if not await self.reverse_sale(str(line["row_kind"]), int(line["row_id"]), recalc=False):
                raise ValueError("Impossible de modifier cette facture.")


        # Insert new lines
        created_lines: list[tuple[str, int]] = []
        for line in lines:
            parts = line.item_key.split(":")
            item_kind = parts[0]
            item_id = int(parts[1])

            created_lines.append(
                await self.create_sale_record(
                    client_id,
                    item_kind,
                    item_id,
                    line.quantity,
                    line.unit,
                    line.unit_price,
                    sale_type,
                    sale_date,
                    notes,
                    0.0 if client_id else line.quantity * line.unit_price,
                    document_id=document_id,
                    custom_item_name=line.custom_item_name,
                )
            )

        # Update document header
        doc = await self.doc_repo.get_by_id(document_id)
        if doc:
            doc.client_id = client_id
            doc.sale_type = sale_type
            doc.sale_date = sale_date
            doc.notes = notes
            self.session.add(doc)

        await self.session.commit()

        after_context = await self.get_sale_document_context(document_id)
        invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
        emit(
            DomainEvent(
                "update",
                "sale_document",
                document_id,
                f"{len(lines)} ligne(s)",
                before=before,
                after=after_context
            )
        )

        return {
            "mode": "document",
            "document_id": document_id,
            "print_doc_type": "sale_document",
            "print_item_id": document_id,
            "line_count": len(lines),
            "first_line_kind": created_lines[0][0],
            "first_line_id": created_lines[0][1],
        }

    async def edit_sale_from_form(self, kind: str, row_id: int, schema: SaleFormSchema) -> dict:
        before = await self.sale_repo.get_sale_detail(kind, row_id)
        if not before:
            raise NotFoundError("Vente", f"{kind}:{row_id}")
        if before.get("document_id"):
            raise ConflictError("Cette ligne appartient déjà à une facture multi-lignes.")

        client_id = schema.client_id
        sale_date = schema.sale_date
        notes = schema.notes
        sale_type = "credit" if client_id else "cash"
        lines = schema.lines

        if len(lines) > 1:
            has_linked = False
            if before.get("client_id"):
                has_linked = await self.sale_repo.line_has_linked_payments(kind, row_id, int(before["client_id"]))
            if has_linked:
                raise ConflictError("Cette facture est déjà liée à des versements.")

            # Reverse the old line
            if not await self.reverse_sale(kind, row_id):
                raise ValueError("Impossible de modifier cette vente.")

            # Create multi-line document
            doc_id = await self._insert_sale_document(client_id, sale_type, sale_date, notes)
            created_lines: list[tuple[str, int]] = []
            for line in lines:
                parts = line.item_key.split(":")
                item_kind = parts[0]
                item_id = int(parts[1])

                created_lines.append(
                    await self.create_sale_record(
                        client_id,
                        item_kind,
                        item_id,
                        line.quantity,
                        line.unit,
                        line.unit_price,
                        sale_type,
                        sale_date,
                        notes,
                        0.0 if client_id else line.quantity * line.unit_price,
                        document_id=doc_id,
                        custom_item_name=line.custom_item_name,
                    )
                )

            await self.session.commit()

            created = await self.doc_repo.get_by_id(doc_id)
            invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
            emit(
                DomainEvent(
                    "update",
                    "sale_document",
                    doc_id,
                    f"{len(lines)} ligne(s)",
                    before=dict(before),
                    after=created.model_dump() if created else None
                )
            )

            return {
                "mode": "document",
                "document_id": doc_id,
                "print_doc_type": "sale_document",
                "print_item_id": doc_id,
                "line_count": len(lines),
                "first_line_kind": created_lines[0][0],
                "first_line_id": created_lines[0][1],
            }

        # Keep as single line sale
        line = lines[0]
        parts = line.item_key.split(":")
        item_kind = parts[0]
        item_id = int(parts[1])

        # Reverse and recreate
        if not await self.reverse_sale(kind, row_id):
            raise ValueError("Impossible de modifier cette vente.")

        new_kind, new_sale_id = await self.create_sale_record(
            client_id,
            item_kind,
            item_id,
            line.quantity,
            line.unit,
            line.unit_price,
            sale_type,
            sale_date,
            notes,
            0.0 if client_id else line.quantity * line.unit_price,
            custom_item_name=line.custom_item_name,
        )

        await self.session.commit()

        after = await self.sale_repo.get_sale_detail(new_kind, new_sale_id)
        invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
        emit(
            DomainEvent(
                "update",
                "sale",
                row_id,
                f"{line.item_kind} #{item_id} qty={line.quantity} {line.unit}",
                before=dict(before),
                after=after
            )
        )

        return {
            "mode": "line",
            "document_id": None,
            "print_doc_type": "sale_finished" if new_kind == "finished" else "sale_raw",
            "print_item_id": new_sale_id,
            "line_count": 1,
            "first_line_kind": new_kind,
            "first_line_id": new_sale_id,
        }

    async def delete_sale_by_id(self, kind: str, row_id: int) -> bool:
        before = await self.sale_repo.get_sale_detail(kind, row_id)
        if not before:
            return False

        ok = await self.reverse_sale(kind, row_id)
        if ok:
            await self.session.commit()
            invalidate_cache_domains("sales_sellable_items", "sales", "client", "dashboard")
            emit(
                DomainEvent(
                    "delete",
                    "sale",
                    row_id,
                    f"Suppression vente {kind}",
                    before=dict(before),
                    after=None
                )
            )
        return ok
