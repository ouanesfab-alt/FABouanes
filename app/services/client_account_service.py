from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select, text, literal, literal_column, func, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat

@async_compat
async def client_balance(client_id: int, db: AsyncSession | None = None) -> float:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _client_balance_impl(client_id, session)
    return await _client_balance_impl(client_id, db)


async def _client_balance_impl(client_id: int, db: AsyncSession) -> float:
    stmt = select(literal_column("current_debt")).select_from(text("clients_with_stats")).where(literal_column("id") == client_id)
    res = await db.execute(stmt)
    row = res.first()
    return float(row[0]) if row else 0.0


@async_compat
async def get_open_credit_entries(client_id: int | None = None, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_open_credit_entries_impl(client_id, session)
    return await _get_open_credit_entries_impl(client_id, db)


async def _get_open_credit_entries_impl(client_id: int | None, db: AsyncSession):
    from app.core.models import Sale, RawSale, Client, FinishedProduct, RawMaterial

    stmt_finished = select(
        literal("finished").label("item_kind"),
        Sale.id,
        Sale.client_id,
        Client.name.label("client_name"),
        FinishedProduct.name.label("item_name"),
        Sale.balance_due,
        Sale.sale_date,
        Sale.total,
        Sale.document_id
    ).join(Client, Client.id == Sale.client_id).join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id).where(Sale.balance_due > 0)

    stmt_raw = select(
        literal("raw").label("item_kind"),
        RawSale.id,
        RawSale.client_id,
        Client.name.label("client_name"),
        func.coalesce(func.nullif(RawSale.custom_item_name, ""), RawMaterial.name).label("item_name"),
        RawSale.balance_due,
        RawSale.sale_date,
        RawSale.total,
        RawSale.document_id
    ).join(Client, Client.id == RawSale.client_id).join(RawMaterial, RawMaterial.id == RawSale.raw_material_id).where(RawSale.balance_due > 0)

    if client_id is not None:
        stmt_finished = stmt_finished.where(Sale.client_id == client_id)
        stmt_raw = stmt_raw.where(RawSale.client_id == client_id)

    union_stmt = union_all(stmt_finished, stmt_raw).subquery()
    stmt = select(union_stmt).order_by(union_stmt.c.sale_date.asc(), union_stmt.c.id.asc())
    res = await db.execute(stmt)
    return [dict(row._mapping) for row in res.fetchall()]


@async_compat
async def apply_payment_to_entry(kind: str, row_id: int, amount: float, entry: dict | None = None, db: AsyncSession | None = None) -> float:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _apply_payment_to_entry_impl(kind, row_id, amount, entry, session)
    return await _apply_payment_to_entry_impl(kind, row_id, amount, entry, db)


async def _apply_payment_to_entry_impl(kind: str, row_id: int, amount: float, entry: dict | None, db: AsyncSession) -> float:
    if amount <= 0:
        return 0.0
    from app.services.stock_service import recalc_sale_document_totals
    from app.core.models import Sale, RawSale

    if kind == "finished":
        if entry is not None:
            balance_due = float(entry["balance_due"])
            document_id = entry.get("document_id")
        else:
            sale_obj = (await db.execute(select(Sale).where(Sale.id == row_id))).scalars().first()
            if not sale_obj:
                return 0.0
            balance_due = float(sale_obj.balance_due)
            document_id = sale_obj.document_id

        paid = min(amount, balance_due)
        await db.execute(
            update(Sale)
            .where(Sale.id == row_id)
            .values(
                balance_due=Sale.balance_due - paid,
                amount_paid=Sale.amount_paid + paid
            )
        )
        await db.flush()
        if document_id:
            await recalc_sale_document_totals(int(document_id), db=db)
        return paid

    if entry is not None:
        balance_due = float(entry["balance_due"])
        document_id = entry.get("document_id")
    else:
        sale_obj = (await db.execute(select(RawSale).where(RawSale.id == row_id))).scalars().first()
        if not sale_obj:
            return 0.0
        balance_due = float(sale_obj.balance_due)
        document_id = sale_obj.document_id

    paid = min(amount, balance_due)
    await db.execute(
        update(RawSale)
        .where(RawSale.id == row_id)
        .values(
            balance_due=RawSale.balance_due - paid,
            amount_paid=RawSale.amount_paid + paid
        )
    )
    await db.flush()
    if document_id:
        await recalc_sale_document_totals(int(document_id), db=db)
    return paid


@async_compat
async def reverse_payment_allocations(payment_row, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _reverse_payment_allocations_impl(payment_row, session)
    return await _reverse_payment_allocations_impl(payment_row, db)


async def _reverse_payment_allocations_impl(payment_row, db: AsyncSession) -> None:
    from app.services.stock_service import recalc_sale_document_totals
    from app.core.models import Sale, RawSale

    meta_raw = payment_row["allocation_meta"] if "allocation_meta" in payment_row.keys() else None
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
                sale_obj = (await db.execute(select(Sale).where(Sale.id == row_id))).scalars().first()
                await db.execute(
                    update(Sale)
                    .where(Sale.id == row_id)
                    .values(
                        amount_paid=Sale.amount_paid - amount,
                        balance_due=Sale.balance_due + amount
                    )
                )
                await db.flush()
                if sale_obj and sale_obj.document_id:
                    await recalc_sale_document_totals(int(sale_obj.document_id), db=db)
            elif kind == "raw":
                sale_obj = (await db.execute(select(RawSale).where(RawSale.id == row_id))).scalars().first()
                await db.execute(
                    update(RawSale)
                    .where(RawSale.id == row_id)
                    .values(
                        amount_paid=RawSale.amount_paid - amount,
                        balance_due=RawSale.balance_due + amount
                    )
                )
                await db.flush()
                if sale_obj and sale_obj.document_id:
                    await recalc_sale_document_totals(int(sale_obj.document_id), db=db)
        return

    if payment_row["payment_type"] != "versement":
        return

    if payment_row["sale_kind"] == "finished" and payment_row["sale_id"]:
        sale_id = payment_row["sale_id"]
        sale_obj = (await db.execute(select(Sale).where(Sale.id == sale_id))).scalars().first()
        await db.execute(
            update(Sale)
            .where(Sale.id == sale_id)
            .values(
                amount_paid=Sale.amount_paid - payment_row["amount"],
                balance_due=Sale.balance_due + payment_row["amount"]
            )
        )
        await db.flush()
        if sale_obj and sale_obj.document_id:
            await recalc_sale_document_totals(int(sale_obj.document_id), db=db)

    elif payment_row["sale_kind"] == "raw" and payment_row["raw_sale_id"]:
        raw_sale_id = payment_row["raw_sale_id"]
        sale_obj = (await db.execute(select(RawSale).where(RawSale.id == raw_sale_id))).scalars().first()
        await db.execute(
            update(RawSale)
            .where(RawSale.id == raw_sale_id)
            .values(
                amount_paid=RawSale.amount_paid - payment_row["amount"],
                balance_due=RawSale.balance_due + payment_row["amount"]
            )
        )
        await db.flush()
        if sale_obj and sale_obj.document_id:
            await recalc_sale_document_totals(int(sale_obj.document_id), db=db)


@async_compat
async def create_payment_record(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    sale_link: str = "",
    payment_type: str = "versement",
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            async with session.begin():
                return await _create_payment_record_impl(client_id, amount, payment_date, notes, sale_link, payment_type, session)
    return await _create_payment_record_impl(client_id, amount, payment_date, notes, sale_link, payment_type, db)


async def _create_payment_record_impl(
    client_id: int,
    amount: float,
    payment_date: str | date,
    notes: str,
    sale_link: str,
    payment_type: str,
    db: AsyncSession,
) -> int:
    from datetime import date
    if isinstance(payment_date, str):
        payment_date = date.fromisoformat(payment_date.strip())

    if amount <= 0:
        raise ValueError("Le montant doit etre superieur a zero.")

    from app.core.models import Client, Payment, Sale, RawSale

    client = (await db.execute(select(Client.id).where(Client.id == client_id).with_for_update())).first()
    if not client:
        raise ValueError("Client introuvable.")


    if payment_type == "avance":
        p = Payment(
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
        db.add(p)
        await db.flush()
        return p.id

    sale_id = None
    raw_sale_id = None
    sale_kind = None
    allocations: list[dict[str, Any]] = []
    applied = 0.0

    if sale_link and ":" in sale_link:
        sale_kind, id_str = sale_link.split(":", 1)
        row_id = int(id_str)
        if sale_kind == "finished":
            entry = (await db.execute(select(Sale.client_id).where(Sale.id == row_id))).first()
        else:
            entry = (await db.execute(select(RawSale.client_id).where(RawSale.id == row_id))).first()

        if entry and int(entry[0] or 0) != client_id:
            raise ValueError("Cette creance ne correspond pas au client choisi.")

        applied = await _apply_payment_to_entry_impl(sale_kind, row_id, amount, None, db)
        if applied <= 0:
            raise ValueError("Aucune creance ouverte a solder pour ce client.")
        allocations = [{"kind": sale_kind, "id": row_id, "amount": applied}]
        if sale_kind == "finished":
            sale_id = row_id
        else:
            raw_sale_id = row_id
    else:
        remaining = amount
        open_entries = await _get_open_credit_entries_impl(client_id, db)
        for entry in open_entries:
            if remaining <= 0:
                break
            paid = await _apply_payment_to_entry_impl(entry["item_kind"], entry["id"], remaining, entry, db)
            if paid > 0:
                allocations.append({"kind": entry["item_kind"], "id": int(entry["id"]), "amount": paid})
                applied += paid
                remaining -= paid
        if applied <= 0 and await _client_balance_impl(client_id, db) <= 0:
            raise ValueError("Aucune dette ouverte pour ce client.")

    p = Payment(
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
    db.add(p)
    await db.flush()
    return p.id
