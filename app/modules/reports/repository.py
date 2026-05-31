"""Requêtes ORM d'agrégation et accès aux données pour le module Rapports."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from decimal import Decimal

from sqlalchemy import select, union_all, func, case, cast, literal_column, String, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Sale, RawSale, Purchase, Payment, Expense, Client, FinishedProduct, RawMaterial

class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sales_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        subq1 = select(
            func.substr(cast(Sale.sale_date, String), 1, 7).label("month"),
            func.sum(Sale.total).label("total_sales"),
            func.sum(Sale.profit_amount).label("total_profit"),
            func.count().label("nb_sales")
        ).group_by(func.substr(cast(Sale.sale_date, String), 1, 7))

        subq2 = select(
            func.substr(cast(RawSale.sale_date, String), 1, 7).label("month"),
            func.sum(RawSale.total).label("total_sales"),
            func.sum(RawSale.profit_amount).label("total_profit"),
            func.count().label("nb_sales")
        ).group_by(func.substr(cast(RawSale.sale_date, String), 1, 7))

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = select(
            union_stmt.c.month,
            func.sum(union_stmt.c.total_sales).label("total"),
            func.sum(union_stmt.c.total_profit).label("profit"),
            func.sum(union_stmt.c.nb_sales).label("count")
        ).group_by(union_stmt.c.month).order_by(union_stmt.c.month.desc()).limit(months)

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_purchases_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        stmt = select(
            func.substr(cast(Purchase.purchase_date, String), 1, 7).label("month"),
            func.sum(Purchase.total).label("total"),
            func.count().label("count")
        ).group_by(func.substr(cast(Purchase.purchase_date, String), 1, 7)).order_by(literal_column("month").desc()).limit(months)

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_top_products_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        # Finished products subquery
        stmt_f = select(
            FinishedProduct.name.label("name"),
            func.sum(Sale.total).label("revenue"),
            func.sum(Sale.profit_amount).label("profit"),
            func.sum(Sale.quantity).label("qty")
        ).select_from(Sale).join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)

        if date_from:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from)
        if date_to:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to)
        stmt_f = stmt_f.group_by(FinishedProduct.name)

        # Raw materials subquery
        stmt_r = select(
            func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("name"),
            func.sum(RawSale.total).label("revenue"),
            func.sum(RawSale.profit_amount).label("profit"),
            func.sum(RawSale.quantity).label("qty")
        ).select_from(RawSale).join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)

        if date_from:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from)
        if date_to:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to)
        stmt_r = stmt_r.group_by(func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name))

        union_stmt = union_all(stmt_f, stmt_r).subquery()

        stmt = select(
            union_stmt.c.name,
            func.sum(union_stmt.c.revenue).label("revenue"),
            func.sum(union_stmt.c.profit).label("profit"),
            func.sum(union_stmt.c.qty).label("qty")
        ).group_by(union_stmt.c.name).order_by(literal_column("revenue").desc()).limit(limit)

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_top_clients_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        # Finished sales subquery
        stmt_f = select(
            Client.name.label("name"),
            func.sum(Sale.total).label("revenue"),
            func.sum(Sale.profit_amount).label("profit"),
            func.count().label("nb")
        ).select_from(Sale).join(Client, Client.id == Sale.client_id).where(Sale.client_id.is_not(None))

        if date_from:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from)
        if date_to:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to)
        stmt_f = stmt_f.group_by(Client.name)

        # Raw sales subquery
        stmt_r = select(
            Client.name.label("name"),
            func.sum(RawSale.total).label("revenue"),
            func.sum(RawSale.profit_amount).label("profit"),
            func.count().label("nb")
        ).select_from(RawSale).join(Client, Client.id == RawSale.client_id).where(RawSale.client_id.is_not(None))

        if date_from:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from)
        if date_to:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to)
        stmt_r = stmt_r.group_by(Client.name)

        union_stmt = union_all(stmt_f, stmt_r).subquery()

        stmt = select(
            union_stmt.c.name,
            func.sum(union_stmt.c.revenue).label("revenue"),
            func.sum(union_stmt.c.profit).label("profit"),
            func.sum(union_stmt.c.nb).label("count")
        ).group_by(union_stmt.c.name).order_by(literal_column("revenue").desc()).limit(limit)

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_period_summary(self, date_from: str | None = None, date_to: str | None = None) -> dict[str, float]:
        # 1. Sales
        stmt_s_total = select(func.coalesce(func.sum(Sale.total), 0))
        stmt_rs_total = select(func.coalesce(func.sum(RawSale.total), 0))
        stmt_s_profit = select(func.coalesce(func.sum(Sale.profit_amount), 0))
        stmt_rs_profit = select(func.coalesce(func.sum(RawSale.profit_amount), 0))
        stmt_s_count = select(func.count(Sale.id))
        stmt_rs_count = select(func.count(RawSale.id))

        if date_from:
            stmt_s_total = stmt_s_total.where(Sale.sale_date >= date_from)
            stmt_rs_total = stmt_rs_total.where(RawSale.sale_date >= date_from)
            stmt_s_profit = stmt_s_profit.where(Sale.sale_date >= date_from)
            stmt_rs_profit = stmt_rs_profit.where(RawSale.sale_date >= date_from)
            stmt_s_count = stmt_s_count.where(Sale.sale_date >= date_from)
            stmt_rs_count = stmt_rs_count.where(RawSale.sale_date >= date_from)

        if date_to:
            stmt_s_total = stmt_s_total.where(Sale.sale_date <= date_to)
            stmt_rs_total = stmt_rs_total.where(RawSale.sale_date <= date_to)
            stmt_s_profit = stmt_s_profit.where(Sale.sale_date <= date_to)
            stmt_rs_profit = stmt_rs_profit.where(RawSale.sale_date <= date_to)
            stmt_s_count = stmt_s_count.where(Sale.sale_date <= date_to)
            stmt_rs_count = stmt_rs_count.where(RawSale.sale_date <= date_to)

        # 2. Purchases
        stmt_p_total = select(func.coalesce(func.sum(Purchase.total), 0))
        stmt_p_count = select(func.count(Purchase.id))
        if date_from:
            stmt_p_total = stmt_p_total.where(Purchase.purchase_date >= date_from)
            stmt_p_count = stmt_p_count.where(Purchase.purchase_date >= date_from)
        if date_to:
            stmt_p_total = stmt_p_total.where(Purchase.purchase_date <= date_to)
            stmt_p_count = stmt_p_count.where(Purchase.purchase_date <= date_to)

        # 3. Payments
        stmt_pay_total = select(func.coalesce(func.sum(Payment.amount), 0))
        stmt_pay_count = select(func.count(Payment.id))
        if date_from:
            stmt_pay_total = stmt_pay_total.where(Payment.payment_date >= date_from)
            stmt_pay_count = stmt_pay_count.where(Payment.payment_date >= date_from)
        if date_to:
            stmt_pay_total = stmt_pay_total.where(Payment.payment_date <= date_to)
            stmt_pay_count = stmt_pay_count.where(Payment.payment_date <= date_to)

        total_sales = (await self.session.execute(stmt_s_total)).scalar_one() + (await self.session.execute(stmt_rs_total)).scalar_one()
        total_profit = (await self.session.execute(stmt_s_profit)).scalar_one() + (await self.session.execute(stmt_rs_profit)).scalar_one()
        nb_sales = (await self.session.execute(stmt_s_count)).scalar_one() + (await self.session.execute(stmt_rs_count)).scalar_one()
        total_purchases = (await self.session.execute(stmt_p_total)).scalar_one()
        nb_purchases = (await self.session.execute(stmt_p_count)).scalar_one()
        total_payments = (await self.session.execute(stmt_pay_total)).scalar_one()
        nb_payments = (await self.session.execute(stmt_pay_count)).scalar_one()

        return {
            "total_sales": float(total_sales),
            "total_profit": float(total_profit),
            "nb_sales": int(nb_sales),
            "total_purchases": float(total_purchases),
            "nb_purchases": int(nb_purchases),
            "total_payments": float(total_payments),
            "nb_payments": int(nb_payments),
        }

    async def get_daily_sales(self, days: int = 30) -> list[dict[str, Any]]:
        cutoff = date.today() - timedelta(days=days)
        subq1 = select(
            Sale.sale_date.label("day"),
            func.sum(Sale.total).label("total"),
            func.sum(Sale.profit_amount).label("profit"),
            func.count().label("nb")
        ).where(Sale.sale_date >= cutoff).group_by(Sale.sale_date)

        subq2 = select(
            RawSale.sale_date.label("day"),
            func.sum(RawSale.total).label("total"),
            func.sum(RawSale.profit_amount).label("profit"),
            func.count().label("nb")
        ).where(RawSale.sale_date >= cutoff).group_by(RawSale.sale_date)

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = select(
            union_stmt.c.day,
            func.sum(union_stmt.c.total).label("total"),
            func.sum(union_stmt.c.profit).label("profit"),
            func.sum(union_stmt.c.nb).label("count")
        ).group_by(union_stmt.c.day).order_by(union_stmt.c.day.asc())

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_expenses_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        try:
            stmt = select(
                func.substr(cast(Expense.date, String), 1, 7).label("month"),
                func.coalesce(func.sum(Expense.amount), 0).label("total"),
                func.count().label("count")
            ).group_by(func.substr(cast(Expense.date, String), 1, 7)).order_by(literal_column("month").desc()).limit(months)

            res = await self.session.execute(stmt)
            return [dict(row) for row in res.mappings().all()]
        except Exception:
            return []

    async def get_expenses_total(self, date_from: str | None = None, date_to: str | None = None) -> float:
        try:
            stmt = select(func.coalesce(func.sum(Expense.amount), 0))
            if date_from:
                stmt = stmt.where(Expense.date >= date_from)
            if date_to:
                stmt = stmt.where(Expense.date <= date_to)

            res = await self.session.execute(stmt)
            return float(res.scalar_one())
        except Exception:
            return 0.0

    async def get_cost_of_goods(self, date_from: str | None = None, date_to: str | None = None) -> float:
        # 1. Sales cost of goods
        stmt_s = select(func.coalesce(func.sum(Sale.quantity * Sale.cost_price_snapshot), 0))
        if date_from:
            stmt_s = stmt_s.where(Sale.sale_date >= date_from)
        if date_to:
            stmt_s = stmt_s.where(Sale.sale_date <= date_to)

        # 2. Raw sales cost of goods
        unit_lower = func.lower(RawSale.unit)
        extracted_num = func.nullif(func.regexp_replace(RawSale.unit, '[^0-9.]', '', 'g'), '')
        sac_multiplier = cast(func.coalesce(extracted_num, '50'), Numeric)

        case_expr = case(
            (unit_lower.like('sac%'), RawSale.quantity * sac_multiplier),
            (unit_lower.in_(['qt', 'quintal']), RawSale.quantity * 100),
            else_=RawSale.quantity
        )

        stmt_rs = select(func.coalesce(func.sum(case_expr * RawSale.cost_price_snapshot), 0))
        if date_from:
            stmt_rs = stmt_rs.where(RawSale.sale_date >= date_from)
        if date_to:
            stmt_rs = stmt_rs.where(RawSale.sale_date <= date_to)

        cogs_sales = (await self.session.execute(stmt_s)).scalar_one()
        cogs_raw = (await self.session.execute(stmt_rs)).scalar_one()

        return float(cogs_sales + cogs_raw)

    async def get_expenses_by_category(self) -> list[dict[str, Any]]:
        try:
            stmt = select(
                Expense.category,
                func.sum(Expense.amount).label("total"),
                func.count().label("count")
            ).group_by(Expense.category).order_by(literal_column("total").desc())

            res = await self.session.execute(stmt)
            return [dict(row) for row in res.mappings().all()]
        except Exception:
            return []

    async def get_clients(self) -> list[dict[str, Any]]:
        stmt = select(Client.id, Client.name, Client.notes, Client.opening_credit)
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_credit_sales(self) -> list[dict[str, Any]]:
        subq1 = select(
            Sale.client_id,
            Sale.sale_date.label("date"),
            Sale.total
        ).where(Sale.client_id.is_not(None), Sale.sale_type == 'credit')

        subq2 = select(
            RawSale.client_id,
            RawSale.sale_date.label("date"),
            RawSale.total
        ).where(RawSale.client_id.is_not(None), RawSale.sale_type == 'credit')

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = select(union_stmt).order_by(union_stmt.c.date.desc())
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_payments(self) -> list[dict[str, Any]]:
        stmt = select(
            Payment.client_id,
            Payment.payment_date.label("date"),
            Payment.amount,
            Payment.payment_type
        ).where(Payment.client_id.is_not(None)).order_by(literal_column("date").asc())

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]
