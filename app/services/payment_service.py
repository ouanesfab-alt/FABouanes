from __future__ import annotations

from datetime import date
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.activity import log_activity
from app.core.audit import audit_event, audit_delete_event
from app.core.helpers import create_payment_record, get_open_credit_entries, reverse_payment_allocations, to_float, async_compat
from app.core.storage import mark_backup_needed
from app.modules.payments.repository import payment_form_context
from app.core.models import Payment, Client, Sale, RawSale, FinishedProduct, RawMaterial


@async_compat
async def new_payment_context(db: AsyncSession | None = None):
    return await payment_form_context(db=db)


@async_compat
async def create_payment_from_form(form, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _create_payment_from_form_impl(form, session)
    return await _create_payment_from_form_impl(form, db)


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
    payment_id = await create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type, db=db)

    created_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    created = created_res.scalar_one_or_none()
    created_dict = created.model_dump() if created else None

    log_activity("create_payment", "payment", payment_id, f"client #{client_id} {payment_type} montant={amount}")
    audit_event("create_payment", "payment", payment_id, after=created_dict)
    mark_backup_needed("create_payment")
    return payment_id, payment_type


@async_compat
async def get_edit_payment_context(payment_id: int, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_edit_payment_context_impl(payment_id, session)
    return await _get_edit_payment_context_impl(payment_id, db)


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

    open_sales = list(await get_open_credit_entries(db=db))
    existing_keys = [f"{sale['item_kind']}:{sale['id']}" for sale in open_sales]

    if current_link and current_link not in existing_keys:
        if payment.get("sale_kind") == "finished" and payment.get("sale_id"):
            stmt = (
                select(
                    Sale.id, Sale.client_id, Client.name.label("client_name"),
                    FinishedProduct.name.label("item_name"),
                    (Sale.balance_due + payment["amount"]).label("balance_due"),
                    Sale.sale_date, Sale.total
                )
                .join(Client, Client.id == Sale.client_id)
                .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
                .where(Sale.id == payment["sale_id"])
            )
            res = await db.execute(stmt)
            sale = res.first()
            if sale:
                open_sales.append(dict(item_kind="finished", id=sale.id, client_id=sale.client_id, client_name=sale.client_name, item_name=sale.item_name, balance_due=sale.balance_due, sale_date=sale.sale_date, total=sale.total))
        elif payment.get("sale_kind") == "raw" and payment.get("raw_sale_id"):
            stmt = (
                select(
                    RawSale.id, RawSale.client_id, Client.name.label("client_name"),
                    func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                    (RawSale.balance_due + payment["amount"]).label("balance_due"),
                    RawSale.sale_date, RawSale.total
                )
                .join(Client, Client.id == RawSale.client_id)
                .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
                .where(RawSale.id == payment["raw_sale_id"])
            )
            res = await db.execute(stmt)
            sale = res.first()
            if sale:
                open_sales.append(dict(item_kind="raw", id=sale.id, client_id=sale.client_id, client_name=sale.client_name, item_name=sale.item_name, balance_due=sale.balance_due, sale_date=sale.sale_date, total=sale.total))

    clients_res = await db.execute(select(Client).order_by(Client.name))
    clients = [c.model_dump() for c in clients_res.scalars().all()]
    return {"payment": payment, "current_link": current_link, "clients": clients, "open_sales": open_sales}


@async_compat
async def edit_payment_from_form(payment_id: int, form, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _edit_payment_from_form_impl(payment_id, form, session)
    return await _edit_payment_from_form_impl(payment_id, form, db)


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

    await reverse_payment_allocations(payment_dict, db=db)
    await db.execute(delete(Payment).where(Payment.id == payment_id))

    new_payment_id = await create_payment_record(client_id, amount, payment_date, notes, sale_link, form.get("payment_type", "versement"), db=db)

    after_res = await db.execute(select(Payment).where(Payment.id == new_payment_id))
    after_obj = after_res.scalar_one_or_none()
    after = after_obj.model_dump() if after_obj else None

    log_activity("update_payment", "payment", payment_id, f"client #{client_id} {form.get('payment_type', 'versement')} montant={amount}")
    audit_event("update_payment", "payment", payment_id, before=before, after=after)
    mark_backup_needed("update_payment")
    return new_payment_id


@async_compat
async def delete_payment_by_id(payment_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _delete_payment_by_id_impl(payment_id, session)
    return await _delete_payment_by_id_impl(payment_id, db)


async def _delete_payment_by_id_impl(payment_id: int, db: AsyncSession) -> bool:
    payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = payment_res.scalar_one_or_none()
    if not payment:
        return False
    payment_dict = payment.model_dump()

    before = dict(payment_dict)
    audit_delete_event("payment", payment_id, before)

    await reverse_payment_allocations(payment_dict, db=db)
    await db.execute(delete(Payment).where(Payment.id == payment_id))

    log_activity("delete_payment", "payment", payment_id, "Suppression transaction client")
    audit_event("delete_payment", "payment", payment_id, before=before, after=None)
    mark_backup_needed("delete_payment")
    return True


@async_compat
async def create_mobile_payment(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    recorded_by: int | None = None,
    db: AsyncSession | None = None,
) -> dict:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _create_mobile_payment_impl(client_id, amount, payment_date, notes, recorded_by, session)
    return await _create_mobile_payment_impl(client_id, amount, payment_date, notes, recorded_by, db)


async def _create_mobile_payment_impl(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    recorded_by: int | None,
    db: AsyncSession,
) -> dict:
    payment_id = await create_payment_record(
        client_id=client_id,
        amount=amount,
        payment_date=payment_date or date.today().isoformat(),
        notes=notes,
        sale_link="",
        payment_type="versement",
        db=db,
    )
    from app.core.audit import audit_event
    from app.modules.users.repository import get_user_by_id

    created_res = await db.execute(select(Payment).where(Payment.id == payment_id))
    created = created_res.scalar_one_or_none()
    created_dict = created.model_dump() if created else None

    log_activity("create_mobile_payment", "payment", payment_id, f"Mobile: client #{client_id} montant={amount} par user #{recorded_by}")

    actor_data = {"id": recorded_by, "username": f"user_{recorded_by}", "role": "operator"}
    if recorded_by:
        try:
            user_info = await get_user_by_id(recorded_by, db=db)
            if user_info:
                actor_data["username"] = user_info.get("username", actor_data["username"])
                actor_data["role"] = user_info.get("role", actor_data["role"])
        except Exception:
            pass

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
