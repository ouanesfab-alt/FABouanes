from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional, Tuple
from sqlmodel import select, func, literal, union_all, literal_column, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, emit
from app.core.exceptions import ValidationError
from app.core.perf_cache import invalidate_cache_domains
from app.core.models import Payment, Sale, RawSale, Client, FinishedProduct, RawMaterial, User
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas_validation import PaymentFormSchema


class PaymentsService:
    """Asynchronous business service layer for the Payments module."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_repo = PaymentRepository(session)

    async def get_client_balance(self, client_id: int) -> float:
        stmt = (
            select(literal_column("current_debt"))
            .select_from(text("clients_with_stats"))
            .where(literal_column("id") == client_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        return float(row._mapping["current_debt"]) if row else 0.0

    async def get_open_credit_entries(self, client_id: int | None = None) -> list[dict]:
        stmt_finished = (
            select(
                literal("finished").label("item_kind"),
                Sale.id,
                Sale.client_id,
                Client.name.label("client_name"),
                FinishedProduct.name.label("item_name"),
                Sale.balance_due,
                Sale.sale_date,
                Sale.total
            )
            .select_from(Sale)
            .join(Client, Client.id == Sale.client_id)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
            .where(Sale.balance_due > 0)
        )
        if client_id is not None:
            stmt_finished = stmt_finished.where(Sale.client_id == client_id)

        stmt_raw = (
            select(
                literal("raw").label("item_kind"),
                RawSale.id,
                RawSale.client_id,
                Client.name.label("client_name"),
                func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                RawSale.balance_due,
                RawSale.sale_date,
                RawSale.total
            )
            .select_from(RawSale)
            .join(Client, Client.id == RawSale.client_id)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .where(RawSale.balance_due > 0)
        )
        if client_id is not None:
            stmt_raw = stmt_raw.where(RawSale.client_id == client_id)

        union_stmt = union_all(stmt_finished, stmt_raw).subquery("x")
        stmt = (
            select(union_stmt)
            .order_by(union_stmt.c.sale_date.asc(), union_stmt.c.id.asc())
        )
        res = await self.session.execute(stmt)
        return [dict(row._mapping) for row in res.fetchall()]

    async def apply_payment_to_entry(self, kind: str, row_id: int, amount: float) -> float:
        if amount <= 0:
            return 0.0
        from app.modules.sales.service import SalesService
        sales_service = SalesService(self.session)
        if kind == "finished":
            stmt = select(Sale).where(Sale.id == row_id).with_for_update()
            res = await self.session.execute(stmt)
            sale = res.scalar_one_or_none()
            if not sale:
                return 0.0
            paid = min(amount, float(sale.balance_due))
            sale.balance_due = float(sale.balance_due) - paid
            sale.amount_paid = float(sale.amount_paid) + paid
            self.session.add(sale)
            await self.session.flush()
            if sale.document_id:
                await sales_service.recalc_sale_document_totals(int(sale.document_id))
            return paid
        else:
            stmt = select(RawSale).where(RawSale.id == row_id).with_for_update()
            res = await self.session.execute(stmt)
            sale = res.scalar_one_or_none()
            if not sale:
                return 0.0
            paid = min(amount, float(sale.balance_due))
            sale.balance_due = float(sale.balance_due) - paid
            sale.amount_paid = float(sale.amount_paid) + paid
            self.session.add(sale)
            await self.session.flush()
            if sale.document_id:
                await sales_service.recalc_sale_document_totals(int(sale.document_id))
            return paid

    async def reverse_payment_allocations(self, payment_row: dict) -> None:
        from app.modules.sales.service import SalesService
        sales_service = SalesService(self.session)
        meta_raw = payment_row.get("allocation_meta")
        if meta_raw:
            try:
                allocations = json.loads(meta_raw)
            except Exception:
                allocations = []
            for allocation in allocations:
                kind = allocation.get("kind")
                row_id = int(allocation.get("id"))
                amount = float(allocation.get("amount", 0) or 0)
                if amount <= 0:
                    continue
                if kind == "finished":
                    stmt = select(Sale).where(Sale.id == row_id).with_for_update()
                    res = await self.session.execute(stmt)
                    doc_row = res.scalar_one_or_none()
                    if doc_row:
                        doc_row.amount_paid = float(doc_row.amount_paid) - amount
                        doc_row.balance_due = float(doc_row.balance_due) + amount
                        self.session.add(doc_row)
                        await self.session.flush()
                        if doc_row.document_id:
                            await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
                elif kind == "raw":
                    stmt = select(RawSale).where(RawSale.id == row_id).with_for_update()
                    res = await self.session.execute(stmt)
                    doc_row = res.scalar_one_or_none()
                    if doc_row:
                        doc_row.amount_paid = float(doc_row.amount_paid) - amount
                        doc_row.balance_due = float(doc_row.balance_due) + amount
                        self.session.add(doc_row)
                        await self.session.flush()
                        if doc_row.document_id:
                            await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
            return

        if payment_row.get("payment_type") != "versement":
            return

        if payment_row.get("sale_kind") == "finished" and payment_row.get("sale_id"):
            sale_id = int(payment_row["sale_id"])
            amount = float(payment_row["amount"])
            stmt = select(Sale).where(Sale.id == sale_id).with_for_update()
            res = await self.session.execute(stmt)
            doc_row = res.scalar_one_or_none()
            if doc_row:
                doc_row.amount_paid = float(doc_row.amount_paid) - amount
                doc_row.balance_due = float(doc_row.balance_due) + amount
                self.session.add(doc_row)
                await self.session.flush()
                if doc_row.document_id:
                    await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
        elif payment_row.get("sale_kind") == "raw" and payment_row.get("raw_sale_id"):
            raw_sale_id = int(payment_row["raw_sale_id"])
            amount = float(payment_row["amount"])
            stmt = select(RawSale).where(RawSale.id == raw_sale_id).with_for_update()
            res = await self.session.execute(stmt)
            doc_row = res.scalar_one_or_none()
            if doc_row:
                doc_row.amount_paid = float(doc_row.amount_paid) - amount
                doc_row.balance_due = float(doc_row.balance_due) + amount
                self.session.add(doc_row)
                await self.session.flush()
                if doc_row.document_id:
                    await sales_service.recalc_sale_document_totals(int(doc_row.document_id))

    async def create_payment_record(
        self,
        client_id: int,
        amount: float,
        payment_date: date | str,
        notes: str,
        sale_link: str = "",
        payment_type: str = "versement"
    ) -> int:
        from datetime import date
        if isinstance(payment_date, str):
            payment_date = date.fromisoformat(payment_date.strip())

        amount = float(amount)
        if amount <= 0:
            raise ValidationError("Le montant doit être supérieur à zéro.")

        # Verify client
        res_client = await self.session.execute(
            select(Client.id).where(Client.id == client_id).with_for_update()
        )

        if not res_client.first():
            raise ValidationError("Client introuvable.")

        if payment_type == "avance":
            p_row = Payment(
                client_id=client_id,
                sale_id=None,
                raw_sale_id=None,
                sale_kind=None,
                payment_type="avance",
                allocation_meta=None,
                amount=amount,
                payment_date=payment_date,
                notes=notes or "Avance client"
            )
            self.session.add(p_row)
            await self.session.flush()
            return p_row.id

        sale_id = None
        raw_sale_id = None
        sale_kind = None
        allocations: list[dict[str, Any]] = []
        applied = 0.0

        if sale_link and ":" in sale_link:
            sale_kind, id_str = sale_link.split(":", 1)
            row_id = int(id_str)
            if sale_kind == "finished":
                stmt = select(Sale.client_id).where(Sale.id == row_id)
            else:
                stmt = select(RawSale.client_id).where(RawSale.id == row_id)
            res_entry = await self.session.execute(stmt)
            entry = res_entry.first()
            if entry and int(entry.client_id or 0) != client_id:
                raise ValidationError("Cette créance ne correspond pas au client choisi.")

            applied = await self.apply_payment_to_entry(sale_kind, row_id, amount)
            if applied <= 0:
                raise ValidationError("Aucune créance ouverte à solder pour ce client.")
            allocations = [{"kind": sale_kind, "id": row_id, "amount": applied}]
            if sale_kind == "finished":
                sale_id = row_id
            else:
                raw_sale_id = row_id
        else:
            remaining = amount
            open_credits = await self.get_open_credit_entries(client_id)
            for entry in open_credits:
                if remaining <= 0:
                    break
                paid = await self.apply_payment_to_entry(entry["item_kind"], entry["id"], remaining)
                if paid > 0:
                    allocations.append({"kind": entry["item_kind"], "id": int(entry["id"]), "amount": paid})
                    applied += paid
                    remaining -= paid
            if applied <= 0:
                balance = await self.get_client_balance(client_id)
                if balance <= 0:
                    raise ValidationError("Aucune dette ouverte pour ce client.")

        p_row = Payment(
            client_id=client_id,
            sale_id=sale_id,
            raw_sale_id=raw_sale_id,
            sale_kind=sale_kind,
            payment_type="versement",
            allocation_meta=json.dumps(allocations) if allocations else None,
            amount=amount,
            payment_date=payment_date,
            notes=notes or "Versement client"
        )
        self.session.add(p_row)
        await self.session.flush()
        return p_row.id

    async def create_payment_from_form(self, schema: PaymentFormSchema) -> Tuple[int, str]:
        client_id = schema.client_id
        sale_link = schema.sale_link
        amount = schema.amount
        payment_date = schema.payment_date
        payment_type = schema.payment_type
        notes = schema.notes

        payment_id = await self.create_payment_record(
            client_id,
            amount,
            payment_date,
            notes,
            sale_link,
            payment_type
        )
        await self.session.commit()

        created = await self.payment_repo.get_by_id(payment_id)
        invalidate_cache_domains("sales", "client", "dashboard")
        emit(
            DomainEvent(
                "create",
                "payment",
                payment_id,
                f"client #{client_id} {payment_type} montant={amount}",
                after=created
            )
        )

        return payment_id, payment_type

    async def get_edit_payment_context(self, payment_id: int) -> Optional[dict]:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return None
        current_link = ""
        if payment.get("sale_kind") == "finished" and payment.get("sale_id"):
            current_link = f"finished:{payment['sale_id']}"
        elif payment.get("sale_kind") == "raw" and payment.get("raw_sale_id"):
            current_link = f"raw:{payment['raw_sale_id']}"

        open_sales = await self.get_open_credit_entries()
        existing_keys = [f"{sale['item_kind']}:{sale['id']}" for sale in open_sales]
        if current_link and current_link not in existing_keys:
            if payment["sale_kind"] == "finished" and payment["sale_id"]:
                stmt = (
                    select(
                        Sale.id,
                        Sale.client_id,
                        Client.name.label("client_name"),
                        FinishedProduct.name.label("item_name"),
                        (Sale.balance_due + payment["amount"]).label("balance_due"),
                        Sale.sale_date,
                        Sale.total
                    )
                    .select_from(Sale)
                    .join(Client, Client.id == Sale.client_id)
                    .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
                    .where(Sale.id == payment["sale_id"])
                )
                res_sale = await self.session.execute(stmt)
                sale = res_sale.first()
                if sale:
                    open_sales.append(dict(sale._mapping))
            elif payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
                stmt = (
                    select(
                        RawSale.id,
                        RawSale.client_id,
                        Client.name.label("client_name"),
                        func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                        (RawSale.balance_due + payment["amount"]).label("balance_due"),
                        RawSale.sale_date,
                        RawSale.total
                    )
                    .select_from(RawSale)
                    .join(Client, Client.id == RawSale.client_id)
                    .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
                    .where(RawSale.id == payment["raw_sale_id"])
                )
                res_sale = await self.session.execute(stmt)
                sale = res_sale.first()
                if sale:
                    open_sales.append(dict(sale._mapping))

        # Fetch clients
        res_clients = await self.session.execute(
            select(*Client.__table__.columns).order_by(Client.name)
        )
        clients = [dict(c._mapping) for c in res_clients.fetchall()]

        return {
            "payment": payment,
            "current_link": current_link,
            "clients": clients,
            "open_sales": open_sales
        }

    async def edit_payment_from_form(self, payment_id: int, schema: PaymentFormSchema) -> int:
        payment = await self.payment_repo.get(payment_id)
        if not payment:
            raise ValidationError("Versement introuvable.")

        # For before meta / event log
        before_dict = await self.payment_repo.get_by_id(payment_id)

        client_id = schema.client_id
        sale_link = schema.sale_link
        amount = schema.amount
        payment_date = schema.payment_date
        notes = schema.notes
        payment_type = schema.payment_type

        # Reverse previous allocations
        await self.reverse_payment_allocations(before_dict)

        # Delete the payment record so we cleanly re-insert/update allocations
        await self.session.delete(payment)
        await self.session.flush()

        new_payment_id = await self.create_payment_record(
            client_id,
            amount,
            payment_date,
            notes,
            sale_link,
            payment_type
        )
        await self.session.commit()

        after = await self.payment_repo.get_by_id(new_payment_id)
        invalidate_cache_domains("sales", "client", "dashboard")
        emit(
            DomainEvent(
                "update",
                "payment",
                new_payment_id,
                f"client #{client_id} {payment_type} montant={amount}",
                before=before_dict,
                after=after
            )
        )
        return new_payment_id

    async def delete_payment_by_id(self, payment_id: int) -> bool:
        payment = await self.payment_repo.get(payment_id)
        if not payment:
            return False

        before_dict = await self.payment_repo.get_by_id(payment_id)

        # Reverse allocations
        await self.reverse_payment_allocations(before_dict)

        # Delete payment record
        await self.session.delete(payment)
        await self.session.commit()

        invalidate_cache_domains("sales", "client", "dashboard")
        emit(
            DomainEvent(
                "delete",
                "payment",
                payment_id,
                "Suppression transaction client",
                before=before_dict,
                after=None
            )
        )
        return True

    async def create_mobile_payment(
        self,
        client_id: int,
        amount: float,
        payment_date: str | date,
        notes: str,
        recorded_by: int | None = None,
    ) -> dict:
        parsed_date = payment_date
        if isinstance(payment_date, str) and payment_date.strip():
            try:
                parsed_date = date.fromisoformat(payment_date.strip())
            except ValueError:
                parsed_date = date.today()
        elif not payment_date:
            parsed_date = date.today()

        payment_id = await self.create_payment_record(
            client_id=client_id,
            amount=amount,
            payment_date=parsed_date,
            notes=notes,
            sale_link="",
            payment_type="versement",
        )
        await self.session.commit()

        created = await self.payment_repo.get_by_id(payment_id)

        # Audit event
        actor_data = {"id": recorded_by, "username": f"user_{recorded_by}", "role": "operator"}
        if recorded_by:
            try:
                res_user = await self.session.execute(
                    select(User.username, User.role).where(User.id == recorded_by)
                )
                user_info = res_user.first()
                if user_info:
                    actor_data["username"] = user_info.username
                    actor_data["role"] = user_info.role
            except Exception:
                pass

        invalidate_cache_domains("sales", "client", "dashboard")
        emit(
            DomainEvent(
                "create",
                "payment",
                payment_id,
                f"Mobile: client #{client_id} montant={amount} par user #{recorded_by}",
                after=created,
                extra={"actor": actor_data},
                source="mobile_api"
            )
        )
        return {"ok": True, "payment_id": payment_id, "payment": created}
