from __future__ import annotations

from typing import Any, Optional
from datetime import date
from sqlmodel import select, func, literal, union_all, literal_column, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Payment, Sale, RawSale, Client, FinishedProduct, RawMaterial
from app.modules.payments.infrastructure.repository import PaymentRepository, payment_form_context


class PaymentsQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Règlements."""

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

    async def get_payment_form_context(self) -> dict:
        return await payment_form_context(db=self.session)
