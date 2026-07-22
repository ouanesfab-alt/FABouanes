from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, func, case, and_, or_, literal, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Payment, Client
from app.core.base_repository import AsyncRepository
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat, db_task_compat, get_open_credit_entries

class PaymentRepository(AsyncRepository[Payment]):
    """Asynchronous repository for the Payment model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)

    async def get_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        sale_ref_expr = case(
            (and_(Payment.sale_kind == 'finished', Payment.sale_id.is_not(None)), literal('Produit #') + cast(Payment.sale_id, String)),
            (and_(Payment.sale_kind == 'raw', Payment.raw_sale_id.is_not(None)), literal('Matière #') + cast(Payment.raw_sale_id, String)),
            else_='-'
        )
        stmt = (
            select(
                *Payment.__table__.columns,
                Client.name.label("client_name"),
                sale_ref_expr.label("sale_ref")
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.client_id)
            .where(Payment.id == payment_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_payments_paginated(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sale_ref_expr = case(
            (and_(Payment.sale_kind == 'finished', Payment.sale_id.is_not(None)), literal('Produit #') + cast(Payment.sale_id, String)),
            (and_(Payment.sale_kind == 'raw', Payment.raw_sale_id.is_not(None)), literal('Matière #') + cast(Payment.raw_sale_id, String)),
            else_='-'
        )

        stmt = (
            select(
                *Payment.__table__.columns,
                Client.name.label("client_name"),
                sale_ref_expr.label("sale_ref")
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.client_id)
        )

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Client.name.ilike(search_pattern),
                    func.coalesce(Payment.notes, '').ilike(search_pattern)
                )
            )

        if date_from:
            stmt = stmt.where(Payment.payment_date >= date_from)
        if date_to:
            stmt = stmt.where(Payment.payment_date <= date_to)

        if kind in {"versement", "avance"}:
            stmt = stmt.where(Payment.payment_type == kind)

        # Count using window function
        stmt = stmt.add_columns(func.count().over().label("_total_count"))

        # Order and paginate
        stmt = (
            stmt.order_by(Payment.payment_date.desc(), Payment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(stmt)
        rows = [dict(row._mapping) for row in result.fetchall()]
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total


# --- Legacy compatibility wrappers ---

@async_compat
async def payment_form_context(db: AsyncSession | None = None) -> dict:
    if db is None:
        async with get_async_sessionmaker()() as sess:
            return await _payment_form_context_impl(sess)
    return await _payment_form_context_impl(db)


async def _payment_form_context_impl(db: AsyncSession) -> dict:
    res = await db.execute(select(Client).order_by(Client.name))
    clients = [c.model_dump() for c in res.scalars().all()]
    open_sales = await get_open_credit_entries()
    return {
        "clients": clients,
        "open_sales": open_sales,
    }


@db_task_compat
async def get_payment(payment_id: int, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_payment_impl(payment_id, session)
    return await _get_payment_impl(payment_id, db)


async def _get_payment_impl(payment_id: int, db: AsyncSession):
    stmt = select(Payment).where(Payment.id == payment_id)
    res = await db.execute(stmt)
    payment = res.scalars().first()
    return payment.model_dump() if payment else None


@async_compat
async def list_payments(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    async with get_async_sessionmaker()() as session:
        repo = PaymentRepository(session)
        return await repo.list_payments_paginated(
            search=search,
            date_from=date_from,
            date_to=date_to,
            kind=kind,
            page=page,
            page_size=page_size
        )
