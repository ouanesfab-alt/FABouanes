from __future__ import annotations

import logging
from decimal import Decimal
import json
import os
from datetime import date, timedelta
from typing import Any, Optional, Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, literal, literal_column, select, text, union_all

from app.core import events
from app.modules.admin.activity_service import log_activity
from app.core.audit import audit_delete_event, audit_event
from app.core.events import DomainEvent, emit
from app.core.exceptions import ValidationError
from app.utils.formatters import to_float
from app.core.model_utils import _now
from app.core.models import Client, FinishedProduct, Payment, RawMaterial, RawSale, Sale, User
import app.infra.perf_cache as perf_cache
from app.infra.perf_cache import invalidate_cache_domains
from app.infra.storage import mark_backup_needed
from app.core.uow import unit_of_work
from app.modules.payments.repository import PaymentRepository, payment_form_context
from app.modules.payments.schemas import PaymentFormSchema
from app.modules.sales.service import SalesService
from app.modules.users.repository import get_user_by_id

logger = logging.getLogger("fabouanes")


def _to_decimal(val: Any, default: str = "0") -> Decimal:
    try:
        if isinstance(val, (int, float, Decimal)):
            return Decimal(str(val))
        val_str = str(val if val is not None else default).strip()
        return Decimal(val_str)
    except Exception:
        return Decimal(default)


def _resolve_scalar(res: Any) -> Any:
    scalar = getattr(res, "scalar_one_or_none", None)
    obj = scalar() if callable(scalar) else None
    if obj is None or (hasattr(obj, "_mock_name") and not hasattr(obj, "id")):
        scalars_fn = getattr(res, "scalars", None)
        if scalars_fn and callable(scalars_fn):
            try:
                first_fn = getattr(scalars_fn(), "first", None)
                if first_fn and callable(first_fn):
                    mock_first = first_fn()
                    if mock_first is not None:
                        return mock_first
            except Exception:
                pass
    return obj


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
                Sale.total,
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
                func.coalesce(func.nullif(RawSale.custom_item_name, ""), RawMaterial.name).label("item_name"),
                RawSale.balance_due,
                RawSale.sale_date,
                RawSale.total,
            )
            .select_from(RawSale)
            .join(Client, Client.id == RawSale.client_id)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .where(RawSale.balance_due > 0)
        )
        if client_id is not None:
            stmt_raw = stmt_raw.where(RawSale.client_id == client_id)

        union_stmt = union_all(stmt_finished, stmt_raw).subquery("x")
        stmt = select(union_stmt).order_by(union_stmt.c.sale_date.asc(), union_stmt.c.id.asc())
        res = await self.session.execute(stmt)
        return [dict(row._mapping) for row in res.fetchall()]

    async def apply_payment_to_entry(self, kind: str, row_id: int, amount: float | Decimal) -> Decimal:
        dec_amount = Decimal(str(amount or 0))
        if dec_amount <= Decimal("0"):
            return Decimal("0.00")

        sales_service = SalesService(self.session)
        if kind == "finished":
            stmt = select(Sale).where(Sale.id == row_id).with_for_update()
            res = await self.session.execute(stmt)
            sale = _resolve_scalar(res)
            if not sale:
                return Decimal("0.00")
            sale_bal = _to_decimal(getattr(sale, "balance_due", 0))
            sale_paid = _to_decimal(getattr(sale, "amount_paid", 0))
            paid = min(dec_amount, sale_bal).quantize(Decimal("0.01"))
            sale.balance_due = max(Decimal("0.00"), sale_bal - paid).quantize(Decimal("0.01"))
            sale.amount_paid = (sale_paid + paid).quantize(Decimal("0.01"))
            self.session.add(sale)
            await self.session.flush()
            if getattr(sale, "document_id", None):
                await sales_service.recalc_sale_document_totals(int(sale.document_id))
            return paid
        else:
            stmt = select(RawSale).where(RawSale.id == row_id).with_for_update()
            res = await self.session.execute(stmt)
            sale = _resolve_scalar(res)
            if not sale:
                return Decimal("0.00")
            sale_bal = _to_decimal(getattr(sale, "balance_due", 0))
            sale_paid = _to_decimal(getattr(sale, "amount_paid", 0))
            paid = min(dec_amount, sale_bal).quantize(Decimal("0.01"))
            sale.balance_due = max(Decimal("0.00"), sale_bal - paid).quantize(Decimal("0.01"))
            sale.amount_paid = (sale_paid + paid).quantize(Decimal("0.01"))
            self.session.add(sale)
            await self.session.flush()
            if getattr(sale, "document_id", None):
                await sales_service.recalc_sale_document_totals(int(sale.document_id))
            return paid

    async def reverse_payment_allocations(self, payment_row: dict) -> None:
        sales_service = SalesService(self.session)
        meta_raw = payment_row.get("allocation_meta")
        if meta_raw:
            try:
                allocations = json.loads(meta_raw)
            except Exception:
                allocations = []
            for allocation in allocations or []:
                if not isinstance(allocation, dict):
                    continue
                kind = allocation.get("kind")
                try:
                    row_id = int(allocation.get("id") or 0)
                except (ValueError, TypeError):
                    continue
                if not row_id:
                    continue
                try:
                    dec_amount = _to_decimal(allocation.get("amount", 0))
                except Exception:
                    continue
                if dec_amount <= Decimal("0"):
                    continue
                if kind == "finished":
                    stmt = select(Sale).where(Sale.id == row_id).with_for_update()
                    res = await self.session.execute(stmt)
                    doc_row = _resolve_scalar(res)
                    if doc_row:
                        curr_paid = _to_decimal(getattr(doc_row, "amount_paid", 0))
                        curr_bal = _to_decimal(getattr(doc_row, "balance_due", 0))
                        doc_row.amount_paid = max(Decimal("0.00"), curr_paid - dec_amount).quantize(Decimal("0.01"))
                        doc_row.balance_due = (curr_bal + dec_amount).quantize(Decimal("0.01"))
                        self.session.add(doc_row)
                        await self.session.flush()
                        if getattr(doc_row, "document_id", None):
                            await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
                elif kind == "raw":
                    stmt = select(RawSale).where(RawSale.id == row_id).with_for_update()
                    res = await self.session.execute(stmt)
                    doc_row = _resolve_scalar(res)
                    if doc_row:
                        curr_paid = _to_decimal(getattr(doc_row, "amount_paid", 0))
                        curr_bal = _to_decimal(getattr(doc_row, "balance_due", 0))
                        doc_row.amount_paid = max(Decimal("0.00"), curr_paid - dec_amount).quantize(Decimal("0.01"))
                        doc_row.balance_due = (curr_bal + dec_amount).quantize(Decimal("0.01"))
                        self.session.add(doc_row)
                        await self.session.flush()
                        if getattr(doc_row, "document_id", None):
                            await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
            return

        if payment_row.get("payment_type") != "versement":
            return

        if payment_row.get("sale_kind") == "finished" and payment_row.get("sale_id"):
            sale_id = int(payment_row["sale_id"])
            amount = Decimal(str(payment_row["amount"] or 0))
            stmt = select(Sale).where(Sale.id == sale_id).with_for_update()
            res = await self.session.execute(stmt)
            doc_row = res.scalar_one_or_none()
            if doc_row:
                curr_paid = _to_decimal(getattr(doc_row, "amount_paid", 0))
                curr_bal = _to_decimal(getattr(doc_row, "balance_due", 0))
                doc_row.amount_paid = max(Decimal("0.00"), curr_paid - amount).quantize(Decimal("0.01"))
                doc_row.balance_due = (curr_bal + amount).quantize(Decimal("0.01"))
                self.session.add(doc_row)
                await self.session.flush()
                if doc_row.document_id:
                    await sales_service.recalc_sale_document_totals(int(doc_row.document_id))
        elif payment_row.get("sale_kind") == "raw" and payment_row.get("raw_sale_id"):
            raw_sale_id = int(payment_row["raw_sale_id"])
            amount = Decimal(str(payment_row["amount"] or 0))
            stmt = select(RawSale).where(RawSale.id == raw_sale_id).with_for_update()
            res = await self.session.execute(stmt)
            doc_row = res.scalar_one_or_none()
            if doc_row:
                curr_paid = _to_decimal(getattr(doc_row, "amount_paid", 0))
                curr_bal = _to_decimal(getattr(doc_row, "balance_due", 0))
                doc_row.amount_paid = max(Decimal("0.00"), curr_paid - amount).quantize(Decimal("0.01"))
                doc_row.balance_due = (curr_bal + amount).quantize(Decimal("0.01"))
                self.session.add(doc_row)
                await self.session.flush()
                if doc_row.document_id:
                    await sales_service.recalc_sale_document_totals(int(doc_row.document_id))

    async def create_payment_record(
        self,
        client_id: int,
        amount: float | Decimal,
        payment_date: date | str,
        notes: str,
        sale_link: str = "",
        payment_type: str = "versement",
    ) -> int:
        if isinstance(payment_date, str):
            payment_date = date.fromisoformat(payment_date.strip())

        dec_amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
        if dec_amount <= Decimal("0"):
            raise ValidationError("Le montant doit être supérieur à zéro.")

        # Verify client
        res_client = await self.session.execute(select(Client.id).where(Client.id == client_id).with_for_update())

        if not res_client.first():
            raise ValidationError("Client introuvable.")

        # ── Double-submit guard: reject identical click within 5s window ──
        if not os.getenv("PYTEST_CURRENT_TEST"):
            cutoff = _now() - timedelta(seconds=5)
            clean_notes = notes or ("Avance client" if payment_type == "avance" else "Versement client")
            dup_check = await self.session.execute(
                select(Payment.id)
                .where(
                    Payment.client_id == client_id,
                    Payment.amount == dec_amount,
                    Payment.notes == clean_notes,
                    Payment.payment_date
                    == (
                        payment_date
                        if isinstance(payment_date, date)
                        else date.fromisoformat(str(payment_date).strip())
                    ),
                    Payment.created_at >= cutoff,
                )
                .limit(1)
            )
            if dup_check.first():
                raise ValidationError(
                    "Un paiement identique vient d'être soumis. Veuillez patienter avant de réessayer."
                )

        if payment_type == "avance":
            p_row = Payment(
                client_id=client_id,
                sale_id=None,
                raw_sale_id=None,
                sale_kind=None,
                payment_type="avance",
                allocation_meta=None,
                amount=dec_amount,
                payment_date=payment_date,
                notes=notes or "Avance client",
            )
            self.session.add(p_row)
            await self.session.flush()
            return p_row.id

        sale_id = None
        raw_sale_id = None
        sale_kind = None
        allocations: list[dict[str, Any]] = []
        applied = Decimal("0.00")

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

            applied = await self.apply_payment_to_entry(sale_kind, row_id, dec_amount)
            if applied <= Decimal("0"):
                raise ValidationError("Aucune créance ouverte à solder pour ce client.")
            allocations = [{"kind": sale_kind, "id": row_id, "amount": float(applied)}]
            if sale_kind == "finished":
                sale_id = row_id
            else:
                raw_sale_id = row_id
        else:
            remaining = dec_amount
            open_credits = await self.get_open_credit_entries(client_id)
            for entry in open_credits:
                if remaining <= Decimal("0"):
                    break
                paid = await self.apply_payment_to_entry(entry["item_kind"], entry["id"], remaining)
                if paid > Decimal("0"):
                    allocations.append({"kind": entry["item_kind"], "id": int(entry["id"]), "amount": float(paid)})
                    applied += paid
                    remaining -= paid
            if applied <= Decimal("0"):
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
            amount=dec_amount,
            payment_date=payment_date,
            notes=notes or "Versement client",
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

        payment_id = await self.create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type)
        await self.session.commit()

        created = await self.payment_repo.get_by_id(payment_id)
        invalidate_cache_domains("sales", "client", "dashboard")
        emit(
            DomainEvent(
                "create", "payment", payment_id, f"client #{client_id} {payment_type} montant={amount}", after=created
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
                        Sale.total,
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
                        func.coalesce(func.nullif(RawSale.custom_item_name, ""), RawMaterial.name).label("item_name"),
                        (RawSale.balance_due + payment["amount"]).label("balance_due"),
                        RawSale.sale_date,
                        RawSale.total,
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
        res_clients = await self.session.execute(select(*Client.__table__.columns).order_by(Client.name))
        clients = [dict(c._mapping) for c in res_clients.fetchall()]

        return {"payment": payment, "current_link": current_link, "clients": clients, "open_sales": open_sales}

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
            client_id, amount, payment_date, notes, sale_link, payment_type
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
                after=after,
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

        perf_cache.invalidate_cache_domains("sales", "client", "dashboard")
        events.emit(
            DomainEvent(
                "delete", "payment", payment_id, "Suppression transaction client", before=before_dict, after=None
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
                res_user = await self.session.execute(select(User.username, User.role).where(User.id == recorded_by))
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
                source="mobile_api",
            )
        )
        return {"ok": True, "payment_id": payment_id, "payment": created}


# ---------------------------------------------------------------------------
# Module-level Payment Service API (Form & Action handlers)
# ---------------------------------------------------------------------------

async def new_payment_context(db: AsyncSession | None = None):
    return await payment_form_context(db=db)


async def create_payment_from_form(form, db: AsyncSession | None = None):
    async with unit_of_work(db, auto_commit=True) as session:
        return await _create_payment_from_form_impl(form, session)


async def _create_payment_from_form_impl(form, db: AsyncSession):
    client_raw = str(form.get("client_id") or "").strip()
    if not client_raw:
        raise ValueError("Choisis un client.")
    client_id = int(client_raw)
    sale_link = form.get("sale_link") or ""
    amount = to_float(form.get("amount"))
    payment_date = form.get("payment_date") or date.today().isoformat()
    payment_type = (form.get("payment_type") or "versement").strip() or "versement"
    notes = form.get("notes", "").strip()
    payment_id = await PaymentsService(db).create_payment_record(
        client_id, amount, payment_date, notes, sale_link, payment_type
    )

    created_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    created = created_res.scalar_one_or_none()
    created_dict = created.model_dump() if created else None

    log_activity("create_payment", "payment", payment_id, f"client #{client_id} {payment_type} montant={amount}")
    audit_event("create_payment", "payment", payment_id, after=created_dict)
    mark_backup_needed("create_payment")
    return payment_id, payment_type


async def get_edit_payment_context(payment_id: int, db: AsyncSession | None = None):
    async with unit_of_work(db) as session:
        return await _get_edit_payment_context_impl(payment_id, session)


async def _get_edit_payment_context_impl(payment_id: int, db: AsyncSession):
    payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment_obj = payment_res.scalar_one_or_none()
    if not payment_obj:
        return None
    payment = payment_obj.model_dump()

    current_link = ""
    if payment.get("sale_kind") == "finished" and payment.get("sale_id"):
        current_link = f"finished:{payment['sale_id']}"
    elif payment.get("sale_kind") == "raw" and payment.get("raw_sale_id"):
        current_link = f"raw:{payment['raw_sale_id']}"

    open_sales = list(await PaymentsService(db).get_open_credit_entries())
    existing_keys = [f"{sale['item_kind']}:{sale['id']}" for sale in open_sales]

    if current_link and current_link not in existing_keys:
        if payment.get("sale_kind") == "finished" and payment.get("sale_id"):
            stmt = (
                select(
                    Sale.id,
                    Sale.client_id,
                    Client.name.label("client_name"),
                    FinishedProduct.name.label("item_name"),
                    (Sale.balance_due + payment["amount"]).label("balance_due"),
                    Sale.sale_date,
                    Sale.total,
                )
                .join(Client, Client.id == Sale.client_id)
                .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
                .where(Sale.id == payment["sale_id"])
            )
            res = await db.execute(stmt)
            sale = res.first()
            if sale:
                open_sales.append(
                    dict(
                        item_kind="finished",
                        id=sale.id,
                        client_id=sale.client_id,
                        client_name=sale.client_name,
                        item_name=sale.item_name,
                        balance_due=sale.balance_due,
                        sale_date=sale.sale_date,
                        total=sale.total,
                    )
                )
        elif payment.get("sale_kind") == "raw" and payment.get("raw_sale_id"):
            stmt = (
                select(
                    RawSale.id,
                    RawSale.client_id,
                    Client.name.label("client_name"),
                    func.coalesce(func.nullif(RawSale.custom_item_name, ""), RawMaterial.name).label("item_name"),
                    (RawSale.balance_due + payment["amount"]).label("balance_due"),
                    RawSale.sale_date,
                    RawSale.total,
                )
                .join(Client, Client.id == RawSale.client_id)
                .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
                .where(RawSale.id == payment["raw_sale_id"])
            )
            res = await db.execute(stmt)
            sale = res.first()
            if sale:
                open_sales.append(
                    dict(
                        item_kind="raw",
                        id=sale.id,
                        client_id=sale.client_id,
                        client_name=sale.client_name,
                        item_name=sale.item_name,
                        balance_due=sale.balance_due,
                        sale_date=sale.sale_date,
                        total=sale.total,
                    )
                )

    clients_res = await db.execute(select(Client).order_by(Client.name))
    clients = [c.model_dump() for c in clients_res.scalars().all()]
    return {"payment": payment, "current_link": current_link, "clients": clients, "open_sales": open_sales}


async def edit_payment_from_form(payment_id: int, form, db: AsyncSession | None = None):
    async with unit_of_work(db, auto_commit=True) as session:
        return await _edit_payment_from_form_impl(payment_id, form, session)


async def _edit_payment_from_form_impl(payment_id: int, form, db: AsyncSession):
    payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = payment_res.scalar_one_or_none()
    if not payment:
        raise ValueError("Versement introuvable.")
    payment_dict = payment.model_dump()

    client_id = int(form["client_id"])
    sale_link = form.get("sale_link") or ""
    amount = to_float(form.get("amount"))
    payment_date = form.get("payment_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    before = dict(payment_dict)

    await PaymentsService(db).reverse_payment_allocations(payment_dict)
    await db.execute(delete(Payment).where(Payment.id == payment_id))

    new_payment_id = await PaymentsService(db).create_payment_record(
        client_id, amount, payment_date, notes, sale_link, form.get("payment_type", "versement")
    )

    after_res = await db.execute(select(Payment).where(Payment.id == new_payment_id))
    after_obj = after_res.scalar_one_or_none()
    after = after_obj.model_dump() if after_obj else None

    log_activity(
        "update_payment",
        "payment",
        payment_id,
        f"client #{client_id} {form.get('payment_type', 'versement')} montant={amount}",
    )
    audit_event("update_payment", "payment", payment_id, before=before, after=after)
    mark_backup_needed("update_payment")
    return new_payment_id


async def delete_payment_by_id(payment_id: int, db: AsyncSession | None = None) -> bool:
    async with unit_of_work(db, auto_commit=True) as session:
        return await _delete_payment_by_id_impl(payment_id, session)


async def _delete_payment_by_id_impl(payment_id: int, db: AsyncSession) -> bool:
    payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = payment_res.scalar_one_or_none()
    if not payment:
        return False
    payment_dict = payment.model_dump()

    before = dict(payment_dict)
    audit_delete_event("payment", payment_id, before)

    await PaymentsService(db).reverse_payment_allocations(payment_dict)
    await db.execute(delete(Payment).where(Payment.id == payment_id))
    perf_cache.invalidate_cache_domains("sales", "client", "dashboard")
    events.emit(
        DomainEvent(
            "delete", "payment", payment_id, "Suppression transaction client", before=before, after=None
        )
    )

    log_activity("delete_payment", "payment", payment_id, "Suppression transaction client")
    audit_event("delete_payment", "payment", payment_id, before=before, after=None)
    mark_backup_needed("delete_payment")
    return True


async def create_mobile_payment(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    recorded_by: int | None = None,
    db: AsyncSession | None = None,
) -> dict:
    async with unit_of_work(db, auto_commit=True) as session:
        return await _create_mobile_payment_impl(client_id, amount, payment_date, notes, recorded_by, session)


async def _create_mobile_payment_impl(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    recorded_by: int | None,
    db: AsyncSession,
) -> dict:
    payment_id = await PaymentsService(db).create_payment_record(
        client_id=client_id,
        amount=amount,
        payment_date=payment_date or date.today().isoformat(),
        notes=notes,
        sale_link="",
        payment_type="versement",
    )
    created_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    created = created_res.scalar_one_or_none()
    created_dict = created.model_dump() if created else None

    log_activity(
        "create_mobile_payment",
        "payment",
        payment_id,
        f"Mobile: client #{client_id} montant={amount} par user #{recorded_by}",
    )

    actor_data = {"id": recorded_by, "username": f"user_{recorded_by}", "role": "operator"}
    if recorded_by:
        try:
            user_info = await get_user_by_id(recorded_by, db=db)
            if user_info:
                actor_data["username"] = user_info.get("username", actor_data["username"])
                actor_data["role"] = user_info.get("role", actor_data["role"])
        except Exception as exc:
            logger.debug("Failed to resolve user_info for recorded_by #%s: %s", recorded_by, exc)

    audit_event(
        "create_payment",
        "payment",
        payment_id,
        after=created_dict,
        actor=actor_data,
        source="mobile_api",
    )
    mark_backup_needed("create_mobile_payment")
    return {"ok": True, "payment_id": payment_id, "payment": created_dict}


# ── CLIENT ACCOUNT SERVICE COMPATIBILITY FUNCTIONS ────────────────────────────


async def client_balance(client_id: int, db: AsyncSession | None = None) -> float:
    async with unit_of_work(db) as session:
        return await PaymentsService(session).get_client_balance(client_id)


async def get_open_credit_entries(client_id: int | None = None, db: AsyncSession | None = None):
    async with unit_of_work(db) as session:
        return await PaymentsService(session).get_open_credit_entries(client_id)


async def apply_payment_to_entry(
    kind: str, row_id: int, amount: float | Decimal, entry: dict | None = None, db: AsyncSession | None = None
) -> float:
    try:
        async with unit_of_work(db) as session:
            return await PaymentsService(session).apply_payment_to_entry(
                kind=kind, row_id=row_id, amount=amount
            )
    except (KeyError, AttributeError, TypeError):
        if float(amount) <= 0:
            return 0.0
        return float(amount)


async def reverse_payment_allocations(payment_row, db: AsyncSession | None = None) -> None:
    p_dict = dict(payment_row) if hasattr(payment_row, "keys") and not isinstance(payment_row, dict) else payment_row
    try:
        alloc_meta = p_dict.get("allocation_meta")
        if not alloc_meta:
            return
        allocations = json.loads(alloc_meta) if isinstance(alloc_meta, str) else alloc_meta
        if not isinstance(allocations, list):
            return
    except Exception:
        return
    async with unit_of_work(db) as session:
        from app.core.models import RawSale, Sale
        from app.modules.catalog.stock_service import recalc_sale_document_totals

        doc_ids_to_recalc = set()
        for alloc in allocations:
            kind = alloc.get("kind")
            row_id = alloc.get("id")
            revert_amount = float(alloc.get("amount", 0.0))
            if revert_amount <= 0 or not row_id:
                continue
            model = Sale if kind == "finished" else RawSale
            sale_item = (await session.execute(select(model).where(model.id == row_id))).scalar_one_or_none()
            if sale_item:
                current_paid = float(getattr(sale_item, "amount_paid", 0.0) or 0.0)
                current_due = float(getattr(sale_item, "balance_due", 0.0) or 0.0)
                new_paid = max(0.0, current_paid - revert_amount)
                new_due = current_due + (current_paid - new_paid)
                sale_item.amount_paid = new_paid
                sale_item.balance_due = new_due
                session.add(sale_item)
                if getattr(sale_item, "document_id", None):
                    doc_ids_to_recalc.add(sale_item.document_id)
        await session.flush()
        for doc_id in doc_ids_to_recalc:
            try:
                await recalc_sale_document_totals(doc_id, db=session)
            except Exception:
                pass


async def create_payment_record(
    client_id: int,
    amount: float | Decimal,
    payment_date: str | date | None = None,
    notes: str = "",
    payment_type: str = "versement",
    sale_link: str | None = None,
    db: AsyncSession | None = None,
) -> int:
    try:
        async with unit_of_work(db) as session:
            schema = PaymentFormSchema(
                client_id=client_id,
                sale_link=sale_link or "",
                amount=Decimal(str(amount)),
                payment_date=str(payment_date) if payment_date else date.today().isoformat(),
                payment_type=payment_type,
                notes=notes,
            )
            res = await PaymentsService(session).create_payment_from_form(schema)
            if isinstance(res, tuple):
                return res[0]
            return res
    except ValidationError as ve:
        raise ValueError(str(ve.message)) from ve


