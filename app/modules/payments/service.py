from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional, Tuple
from sqlmodel import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, emit
from app.core.exceptions import ValidationError
from app.core.perf_cache import invalidate_cache_domains
from app.core.models import Payment
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas_validation import PaymentFormSchema


class PaymentsService:
    """Asynchronous business service layer for the Payments module."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_repo = PaymentRepository(session)

    async def get_client_balance(self, client_id: int) -> float:
        res = await self.session.execute(
            text("SELECT current_debt FROM clients_with_stats WHERE id = :client_id"),
            {"client_id": client_id}
        )
        row = res.first()
        return float(row.current_debt) if row else 0.0

    async def get_open_credit_entries(self, client_id: int | None = None) -> list[dict]:
        params: dict[str, Any] = {}
        where_sales = "WHERE s.balance_due > 0"
        where_raw = "WHERE rs.balance_due > 0"
        if client_id is not None:
            where_sales += " AND s.client_id = :client_id"
            where_raw += " AND rs.client_id = :client_id"
            params["client_id"] = client_id

        res = await self.session.execute(
            text(f"""
                SELECT * FROM (
                    SELECT 'finished' AS item_kind, s.id, s.client_id, c.name AS client_name, f.name AS item_name,
                           s.balance_due, s.sale_date, s.total
                    FROM sales s
                    JOIN clients c ON c.id = s.client_id
                    JOIN finished_products f ON f.id = s.finished_product_id
                    {where_sales}
                    UNION ALL
                    SELECT 'raw' AS item_kind, rs.id, rs.client_id, c.name AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                           rs.balance_due, rs.sale_date, rs.total
                    FROM raw_sales rs
                    JOIN clients c ON c.id = rs.client_id
                    JOIN raw_materials r ON r.id = rs.raw_material_id
                    {where_raw}
                ) x
                ORDER BY sale_date ASC, id ASC
            """),
            params
        )
        return [dict(row._mapping) for row in res.fetchall()]

    async def apply_payment_to_entry(self, kind: str, row_id: int, amount: float) -> float:
        if amount <= 0:
            return 0.0
        from app.modules.sales.service import SalesService
        sales_service = SalesService(self.session)
        if kind == "finished":
            res = await self.session.execute(
                text("SELECT balance_due, document_id FROM sales WHERE id = :id FOR UPDATE"),
                {"id": row_id}
            )
            sale = res.first()
            if not sale:
                return 0.0
            paid = min(amount, float(sale.balance_due))
            await self.session.execute(
                text("UPDATE sales SET balance_due = balance_due - :paid, amount_paid = amount_paid + :paid WHERE id = :id"),
                {"paid": paid, "id": row_id}
            )
            if sale.document_id:
                await sales_service.recalc_sale_document_totals(int(sale.document_id))
            return paid
        else:
            res = await self.session.execute(
                text("SELECT balance_due, document_id FROM raw_sales WHERE id = :id FOR UPDATE"),
                {"id": row_id}
            )
            sale = res.first()
            if not sale:
                return 0.0
            paid = min(amount, float(sale.balance_due))
            await self.session.execute(
                text("UPDATE raw_sales SET balance_due = balance_due - :paid, amount_paid = amount_paid + :paid WHERE id = :id"),
                {"paid": paid, "id": row_id}
            )
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
                    res = await self.session.execute(
                        text("SELECT document_id FROM sales WHERE id = :id FOR UPDATE"),
                        {"id": row_id}
                    )
                    doc_row = res.first()
                    await self.session.execute(
                        text("UPDATE sales SET amount_paid = amount_paid - :amount, balance_due = balance_due + :amount WHERE id = :id"),
                        {"amount": amount, "id": row_id}
                    )
                    if doc_row and doc_row.document_id:
                        await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
                elif kind == "raw":
                    res = await self.session.execute(
                        text("SELECT document_id FROM raw_sales WHERE id = :id FOR UPDATE"),
                        {"id": row_id}
                    )
                    doc_row = res.first()
                    await self.session.execute(
                        text("UPDATE raw_sales SET amount_paid = amount_paid - :amount, balance_due = balance_due + :amount WHERE id = :id"),
                        {"amount": amount, "id": row_id}
                    )
                    if doc_row and doc_row.document_id:
                        await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
            return

        if payment_row.get("payment_type") != "versement":
            return

        if payment_row.get("sale_kind") == "finished" and payment_row.get("sale_id"):
            sale_id = int(payment_row["sale_id"])
            amount = float(payment_row["amount"])
            res = await self.session.execute(
                text("SELECT document_id FROM sales WHERE id = :id FOR UPDATE"),
                {"id": sale_id}
            )
            doc_row = res.first()
            await self.session.execute(
                text("UPDATE sales SET amount_paid = amount_paid - :amount, balance_due = balance_due + :amount WHERE id = :id"),
                {"amount": amount, "id": sale_id}
            )
            if doc_row and doc_row.document_id:
                await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
        elif payment_row.get("sale_kind") == "raw" and payment_row.get("raw_sale_id"):
            raw_sale_id = int(payment_row["raw_sale_id"])
            amount = float(payment_row["amount"])
            res = await self.session.execute(
                text("SELECT document_id FROM raw_sales WHERE id = :id FOR UPDATE"),
                {"id": raw_sale_id}
            )
            doc_row = res.first()
            await self.session.execute(
                text("UPDATE raw_sales SET amount_paid = amount_paid - :amount, balance_due = balance_due + :amount WHERE id = :id"),
                {"amount": amount, "id": raw_sale_id}
            )
            if doc_row and doc_row.document_id:
                await sales_service.recalc_sale_document_totals(int(doc_row.document_id))

    async def create_payment_record(
        self,
        client_id: int,
        amount: float,
        payment_date: date,
        notes: str,
        sale_link: str = "",
        payment_type: str = "versement"
    ) -> int:
        amount = float(amount)
        if amount <= 0:
            raise ValidationError("Le montant doit être supérieur à zéro.")
        
        # Verify client
        res_client = await self.session.execute(
            text("SELECT id FROM clients WHERE id = :client_id"),
            {"client_id": client_id}
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
                stmt = text("SELECT client_id FROM sales WHERE id = :id")
            else:
                stmt = text("SELECT client_id FROM raw_sales WHERE id = :id")
            res_entry = await self.session.execute(stmt, {"id": row_id})
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
                res_sale = await self.session.execute(
                    text("""
                        SELECT s.id, s.client_id, c.name AS client_name, f.name AS item_name, 
                               s.balance_due + :amount AS balance_due, s.sale_date, s.total 
                        FROM sales s 
                        JOIN clients c ON c.id=s.client_id 
                        JOIN finished_products f ON f.id=s.finished_product_id 
                        WHERE s.id=:sale_id
                    """),
                    {"amount": payment["amount"], "sale_id": payment["sale_id"]}
                )
                sale = res_sale.first()
                if sale:
                    open_sales.append(dict(sale._mapping))
            elif payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
                res_sale = await self.session.execute(
                    text("""
                        SELECT rs.id, rs.client_id, c.name AS client_name, 
                               COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, 
                               rs.balance_due + :amount AS balance_due, rs.sale_date, rs.total 
                        FROM raw_sales rs 
                        JOIN clients c ON c.id=rs.client_id 
                        JOIN raw_materials r ON r.id=rs.raw_material_id 
                        WHERE rs.id=:raw_sale_id
                    """),
                    {"amount": payment["amount"], "raw_sale_id": payment["raw_sale_id"]}
                )
                sale = res_sale.first()
                if sale:
                    open_sales.append(dict(sale._mapping))

        # Fetch clients
        res_clients = await self.session.execute(
            text("SELECT * FROM clients ORDER BY name")
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
                    text("SELECT username, role FROM users WHERE id = :id"),
                    {"id": recorded_by}
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
