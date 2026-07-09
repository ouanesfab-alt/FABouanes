"""Requêtes ORM d'agrégation et accès aux données pour le module Rapports."""
from __future__ import annotations

from datetime import date, timedelta
import time
from typing import Any

from sqlalchemy import select, union_all, func, case, cast, literal_column, String, Numeric, text, true
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import db_task_compat
from app.core.perf_cache import async_cached_result, TTL_FREQUENT, TTL_SEMI_STABLE
from app.core.models import Sale, RawSale, Purchase, Payment, Expense, Client, FinishedProduct, RawMaterial, Supplier, ProductionBatch, ProductionBatchItem

class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sales_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        subq1 = select(
            func.substr(cast(Sale.sale_date, String), 1, 7).label("month"),
            func.sum(Sale.total).label("total_sales"),
            func.sum(Sale.profit_amount).label("total_profit"),
            func.count().label("nb_sales")
        ).group_by(literal_column("month"))

        subq2 = select(
            func.substr(cast(RawSale.sale_date, String), 1, 7).label("month"),
            func.sum(RawSale.total).label("total_sales"),
            func.sum(RawSale.profit_amount).label("total_profit"),
            func.count().label("nb_sales")
        ).group_by(literal_column("month"))

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
        ).group_by(literal_column("month")).order_by(literal_column("month").desc()).limit(months)

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_top_products_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # Finished products subquery
        stmt_f = select(
            FinishedProduct.name.label("name"),
            func.sum(Sale.total).label("revenue"),
            func.sum(Sale.profit_amount).label("profit"),
            func.sum(Sale.quantity).label("qty")
        ).select_from(Sale).join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)

        if date_from_val:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from_val)
        if date_to_val:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to_val)
        stmt_f = stmt_f.group_by(FinishedProduct.name)

        # Raw materials subquery
        stmt_r = select(
            func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("name"),
            func.sum(RawSale.total).label("revenue"),
            func.sum(RawSale.profit_amount).label("profit"),
            func.sum(RawSale.quantity).label("qty")
        ).select_from(RawSale).join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)

        if date_from_val:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to_val)
        stmt_r = stmt_r.group_by(RawSale.custom_item_name, RawMaterial.name)

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
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # Finished sales subquery
        stmt_f = select(
            Client.name.label("name"),
            func.sum(Sale.total).label("revenue"),
            func.sum(Sale.profit_amount).label("profit"),
            func.count().label("nb")
        ).select_from(Sale).join(Client, Client.id == Sale.client_id).where(Sale.client_id.is_not(None))

        if date_from_val:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from_val)
        if date_to_val:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to_val)
        stmt_f = stmt_f.group_by(Client.name)

        # Raw sales subquery
        stmt_r = select(
            Client.name.label("name"),
            func.sum(RawSale.total).label("revenue"),
            func.sum(RawSale.profit_amount).label("profit"),
            func.count().label("nb")
        ).select_from(RawSale).join(Client, Client.id == RawSale.client_id).where(RawSale.client_id.is_not(None))

        if date_from_val:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to_val)
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
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # 1. Sales
        stmt_s_total = select(func.coalesce(func.sum(Sale.total), 0))
        stmt_rs_total = select(func.coalesce(func.sum(RawSale.total), 0))
        stmt_s_profit = select(func.coalesce(func.sum(Sale.profit_amount), 0))
        stmt_rs_profit = select(func.coalesce(func.sum(RawSale.profit_amount), 0))
        stmt_s_count = select(func.count(Sale.id))
        stmt_rs_count = select(func.count(RawSale.id))

        if date_from_val:
            stmt_s_total = stmt_s_total.where(Sale.sale_date >= date_from_val)
            stmt_rs_total = stmt_rs_total.where(RawSale.sale_date >= date_from_val)
            stmt_s_profit = stmt_s_profit.where(Sale.sale_date >= date_from_val)
            stmt_rs_profit = stmt_rs_profit.where(RawSale.sale_date >= date_from_val)
            stmt_s_count = stmt_s_count.where(Sale.sale_date >= date_from_val)
            stmt_rs_count = stmt_rs_count.where(RawSale.sale_date >= date_from_val)

        if date_to_val:
            stmt_s_total = stmt_s_total.where(Sale.sale_date <= date_to_val)
            stmt_rs_total = stmt_rs_total.where(RawSale.sale_date <= date_to_val)
            stmt_s_profit = stmt_s_profit.where(Sale.sale_date <= date_to_val)
            stmt_rs_profit = stmt_rs_profit.where(RawSale.sale_date <= date_to_val)
            stmt_s_count = stmt_s_count.where(Sale.sale_date <= date_to_val)
            stmt_rs_count = stmt_rs_count.where(RawSale.sale_date <= date_to_val)

        # 2. Purchases
        stmt_p_total = select(func.coalesce(func.sum(Purchase.total), 0))
        stmt_p_count = select(func.count(Purchase.id))
        if date_from_val:
            stmt_p_total = stmt_p_total.where(Purchase.purchase_date >= date_from_val)
            stmt_p_count = stmt_p_count.where(Purchase.purchase_date >= date_from_val)
        if date_to_val:
            stmt_p_total = stmt_p_total.where(Purchase.purchase_date <= date_to_val)
            stmt_p_count = stmt_p_count.where(Purchase.purchase_date <= date_to_val)

        # 3. Payments
        stmt_pay_total = select(func.coalesce(func.sum(Payment.amount), 0))
        stmt_pay_count = select(func.count(Payment.id))
        if date_from_val:
            stmt_pay_total = stmt_pay_total.where(Payment.payment_date >= date_from_val)
            stmt_pay_count = stmt_pay_count.where(Payment.payment_date >= date_from_val)
        if date_to_val:
            stmt_pay_total = stmt_pay_total.where(Payment.payment_date <= date_to_val)
            stmt_pay_count = stmt_pay_count.where(Payment.payment_date <= date_to_val)

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
            ).group_by(literal_column("month")).order_by(literal_column("month").desc()).limit(months)

            res = await self.session.execute(stmt)
            return [dict(row) for row in res.mappings().all()]
        except Exception:
            return []

    async def get_expenses_total(self, date_from: str | None = None, date_to: str | None = None) -> float:
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        try:
            stmt = select(func.coalesce(func.sum(Expense.amount), 0))
            if date_from_val:
                stmt = stmt.where(Expense.date >= date_from_val)
            if date_to_val:
                stmt = stmt.where(Expense.date <= date_to_val)

            res = await self.session.execute(stmt)
            return float(res.scalar_one())
        except Exception:
            return 0.0

    async def get_cost_of_goods(self, date_from: str | None = None, date_to: str | None = None) -> float:
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # 1. Sales cost of goods
        stmt_s = select(func.coalesce(func.sum(Sale.quantity * Sale.cost_price_snapshot), 0))
        if date_from_val:
            stmt_s = stmt_s.where(Sale.sale_date >= date_from_val)
        if date_to_val:
            stmt_s = stmt_s.where(Sale.sale_date <= date_to_val)

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
        if date_from_val:
            stmt_rs = stmt_rs.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_rs = stmt_rs.where(RawSale.sale_date <= date_to_val)

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


# --- Dashboard Queries (migrated from dashboard_repository) ---

@db_task_compat
async def get_dashboard_snapshot(target_date: str | None = None, db: AsyncSession | None = None) -> dict:
    resolved_date = target_date or date.today().isoformat()
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _build_dashboard_snapshot(resolved_date, session)
        return await _build_dashboard_snapshot(resolved_date, db)
    return await async_cached_result(
        ("dashboard_snapshot", resolved_date),
        load,
        ttl_seconds=45.0,
    )


@db_task_compat
async def get_kpis_for_date(target_date: str, db: AsyncSession | None = None) -> dict[str, float | str]:
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _build_kpis_for_date(target_date, session)
        return await _build_kpis_for_date(target_date, db)
    return await async_cached_result(
        ("dashboard_kpis", target_date),
        load,
        ttl_seconds=45.0,
    )


async def _build_dashboard_snapshot(today: str, db: AsyncSession) -> dict:
    target_day = date.fromisoformat(today)
    cutoff_30d = (target_day - timedelta(days=30)).isoformat()
    week_iso = (target_day - timedelta(days=7)).isoformat()

    daily_sum = await _dashboard_daily_summary(today, week_iso, db)
    cum_sum = await _dashboard_cumulative_summary(db)
    summary = {**daily_sum, **cum_sum}

    # Low stock query
    async def load_low_stock():
        low_stock_query = select(RawMaterial).where(RawMaterial.stock_qty <= RawMaterial.alert_threshold).order_by(RawMaterial.stock_qty.asc())
        res = await db.execute(low_stock_query)
        return [r.model_dump() for r in res.scalars().all()]

    low_stock = await async_cached_result(
        ("dashboard", "low_stock"),
        load_low_stock,
        ttl_seconds=TTL_FREQUENT,
    )

    # Recent sales query
    async def load_recent_sales():
        finished_sub = (
            select(
                Sale.sale_date,
                func.coalesce(Client.name, 'Comptoir').label("client_name"),
                FinishedProduct.name.label("item_name"),
                Sale.total,
                Sale.balance_due,
                Sale.profit_amount,
                literal_column("'Produit final'").label("source")
            )
            .select_from(Sale)
            .outerjoin(Client, Client.id == Sale.client_id)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
            .order_by(Sale.sale_date.desc(), Sale.id.desc())
            .limit(15)
            .subquery()
        )

        raw_sub = (
            select(
                RawSale.sale_date,
                func.coalesce(Client.name, 'Comptoir').label("client_name"),
                func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                RawSale.total,
                RawSale.balance_due,
                RawSale.profit_amount,
                literal_column("'Matiere premiere'").label("source")
            )
            .select_from(RawSale)
            .outerjoin(Client, Client.id == RawSale.client_id)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .order_by(RawSale.sale_date.desc(), RawSale.id.desc())
            .limit(15)
            .subquery()
        )

        recent_query = (
            select(
                finished_sub.c.sale_date,
                finished_sub.c.client_name,
                finished_sub.c.item_name,
                finished_sub.c.total,
                finished_sub.c.balance_due,
                finished_sub.c.profit_amount,
                finished_sub.c.source
            )
            .union_all(
                select(
                    raw_sub.c.sale_date,
                    raw_sub.c.client_name,
                    raw_sub.c.item_name,
                    raw_sub.c.total,
                    raw_sub.c.balance_due,
                    raw_sub.c.profit_amount,
                    raw_sub.c.source
                )
            )
            .order_by(literal_column("sale_date").desc())
            .limit(10)
        )
        res = await db.execute(recent_query)
        return [dict(r._mapping) for r in res.all()]

    recent_sales = await async_cached_result(
        ("dashboard", "recent_sales"),
        load_recent_sales,
        ttl_seconds=TTL_FREQUENT,
    )

    # Counts query
    async def load_counts():
        counts_query = select(
            select(func.count()).select_from(Client).scalar_subquery().label("clients"),
            select(func.count()).select_from(Supplier).scalar_subquery().label("suppliers"),
            select(func.count()).select_from(RawMaterial).scalar_subquery().label("raw_materials"),
            select(func.count()).select_from(FinishedProduct).scalar_subquery().label("products"),
        )
        res = await db.execute(counts_query)
        row = res.first()
        return dict(row._mapping) if row else {}

    counts = await async_cached_result(
        ("dashboard", "counts"),
        load_counts,
        ttl_seconds=TTL_FREQUENT,
    )

    # Sales summary query
    async def load_sales_summary():
        f_sub = select(
            Sale.sale_date,
            func.count().label("nb_sales"),
            func.sum(Sale.total).label("total_sales"),
            func.sum(Sale.amount_paid).label("total_paid"),
            func.sum(Sale.balance_due).label("total_due"),
            func.sum(Sale.profit_amount).label("total_profit")
        ).group_by(Sale.sale_date)

        r_sub = select(
            RawSale.sale_date,
            func.count().label("nb_sales"),
            func.sum(RawSale.total).label("total_sales"),
            func.sum(RawSale.amount_paid).label("total_paid"),
            func.sum(RawSale.balance_due).label("total_due"),
            func.sum(RawSale.profit_amount).label("total_profit")
        ).group_by(RawSale.sale_date)

        union_sub = union_all(f_sub, r_sub).subquery("union_sub")

        sales_summary_query = select(
            union_sub.c.sale_date,
            func.sum(union_sub.c.nb_sales).label("nb_sales"),
            func.sum(union_sub.c.total_sales).label("total_sales"),
            func.sum(union_sub.c.total_paid).label("total_paid"),
            func.sum(union_sub.c.total_due).label("total_due"),
            func.sum(union_sub.c.total_profit).label("total_profit")
        ).group_by(union_sub.c.sale_date).order_by(union_sub.c.sale_date.desc()).limit(15)

        res = await db.execute(sales_summary_query)
        return [dict(r._mapping) for r in res.all()]

    sales_summary = await async_cached_result(
        ("dashboard", "sales_summary"),
        load_sales_summary,
        ttl_seconds=TTL_FREQUENT,
    )

    async def load_stock_materials():
        return await _build_stock_materials(cutoff_30d, db)

    stock_materials = await async_cached_result(
        ("dashboard", "stock_materials", cutoff_30d),
        load_stock_materials,
        ttl_seconds=TTL_FREQUENT,
    )

    async def load_stock_products():
        stock_products_query = select(FinishedProduct).order_by(FinishedProduct.name).limit(10)
        res = await db.execute(stock_products_query)
        return [r.model_dump() for r in res.scalars().all()]

    stock_products = await async_cached_result(
        ("dashboard", "stock_products"),
        load_stock_products,
        ttl_seconds=TTL_FREQUENT,
    )

    today_value = float(summary["sales_today"])
    week_value = float(summary["sales_week_ago"])
    sales_delta_pct = round((today_value - week_value) / week_value * 100, 1) if week_value > 0 else None

    async def load_debt_by_client():
        return await _build_debt_by_client(db)

    debt_by_client = await async_cached_result(
        ("dashboard", "debt_by_client"),
        load_debt_by_client,
        ttl_seconds=TTL_FREQUENT,
    )

    async def load_production_history():
        production_history_query = select(
            ProductionBatch.production_date,
            FinishedProduct.name.label("product_name"),
            ProductionBatch.output_quantity,
            ProductionBatch.production_cost,
            ProductionBatch.unit_cost
        ).join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id).order_by(ProductionBatch.id.desc()).limit(10)
        res = await db.execute(production_history_query)
        return [dict(r._mapping) for r in res.all()]

    production_history = await async_cached_result(
        ("dashboard", "production_history"),
        load_production_history,
        ttl_seconds=TTL_SEMI_STABLE,
    )

    return {
        "today": today,
        "sales_today": summary["sales_today"],
        "cash_today": summary["cash_today"],
        "total_receivables": summary["total_receivables"],
        "profit_today": summary["profit_today"],
        "total_profit": summary["total_profit"],
        "low_stock": low_stock,
        "recent_sales": recent_sales,
        "counts": dict(counts or {}),
        "sales_summary": sales_summary,
        "stock_materials": stock_materials,
        "stock_products": stock_products,
        "sales_delta_pct": sales_delta_pct,
        "profit_stats": {
            "revenue": summary["revenue"],
            "cost_of_goods": summary["cost_of_goods"],
            "gross_profit": summary["gross_profit"],
        },
        "debt_by_client": debt_by_client,
        "production_history": production_history,
    }


async def _build_stock_materials(cutoff_30d: str, db: AsyncSession) -> list[dict]:
    cutoff_date = date.fromisoformat(cutoff_30d) if isinstance(cutoff_30d, str) else cutoff_30d
    raw_sale_qty_expr = case(
        (func.lower(RawSale.unit).like('sac%'), RawSale.quantity * func.coalesce(func.nullif(func.regexp_replace(RawSale.unit, '[^0-9.]', '', 'g'), '').cast(Numeric), 50)),
        (func.lower(RawSale.unit).in_(['qt', 'quintal']), RawSale.quantity * 100),
        else_=RawSale.quantity
    )

    raw_sale_sub = select(
        RawSale.raw_material_id,
        raw_sale_qty_expr.label("qty")
    ).where(RawSale.sale_date >= cutoff_date)

    prod_sub = select(
        ProductionBatchItem.raw_material_id,
        ProductionBatchItem.quantity.label("qty")
    ).join(ProductionBatch, ProductionBatch.id == ProductionBatchItem.batch_id).where(ProductionBatch.production_date >= cutoff_date)

    source_union = union_all(raw_sale_sub, prod_sub).subquery("source_union")

    consumed_sub = select(
        source_union.c.raw_material_id,
        func.sum(source_union.c.qty).label("consumed_30d")
    ).group_by(source_union.c.raw_material_id).subquery("consumed")

    stock_materials_query = select(
        *RawMaterial.__table__.columns,
        func.coalesce(consumed_sub.c.consumed_30d, 0).label("consumed_30d")
    ).select_from(RawMaterial).outerjoin(consumed_sub, consumed_sub.c.raw_material_id == RawMaterial.id).order_by(RawMaterial.name).limit(15)

    res = await db.execute(stock_materials_query)
    stock_materials_raw = res.all()
    result = []
    for material in stock_materials_raw:
        row = dict(material._mapping)
        daily = float(row.get("consumed_30d") or 0) / 30.0
        row["days_left"] = int(round(float(row["stock_qty"]) / daily)) if daily > 0.01 else None
        result.append(row)
    return result


async def _build_debt_by_client(db: AsyncSession) -> list:
    try:
        mv_query = select(
            literal_column("client_id").label("id"),
            literal_column("name"),
            literal_column("balance")
        ).select_from(text("mv_client_balances")).where(literal_column("balance") > 0).order_by(literal_column("balance").desc()).limit(10)
        res = await db.execute(mv_query)
        return [dict(r._mapping) for r in res.all()]
    except Exception:
        pass

    finished_totals = select(
        Sale.client_id,
        func.sum(Sale.total).label("credit_total")
    ).where(Sale.client_id.is_not(None), Sale.sale_type == 'credit').group_by(Sale.client_id).cte("finished_totals")

    raw_totals = select(
        RawSale.client_id,
        func.sum(RawSale.total).label("credit_total")
    ).where(RawSale.client_id.is_not(None), RawSale.sale_type == 'credit').group_by(RawSale.client_id).cte("raw_totals")

    payment_totals = select(
        Payment.client_id,
        func.sum(case((Payment.payment_type == 'versement', Payment.amount), else_=0)).label("versements"),
        func.sum(case((Payment.payment_type == 'avance', Payment.amount), else_=0)).label("avances")
    ).group_by(Payment.client_id).cte("payment_totals")

    balance_expr = (
        Client.opening_credit +
        func.coalesce(finished_totals.c.credit_total, 0) +
        func.coalesce(raw_totals.c.credit_total, 0) -
        func.coalesce(payment_totals.c.versements, 0) +
        func.coalesce(payment_totals.c.avances, 0)
    )

    fallback_query = select(
        Client.id,
        Client.name,
        balance_expr.label("balance")
    ).select_from(Client).outerjoin(
        finished_totals, finished_totals.c.client_id == Client.id
    ).outerjoin(
        raw_totals, raw_totals.c.client_id == Client.id
    ).outerjoin(
        payment_totals, payment_totals.c.client_id == Client.id
    ).where(balance_expr > 0).order_by(literal_column("balance").desc()).limit(10)

    res = await db.execute(fallback_query)
    return [dict(r._mapping) for r in res.all()]


_LAST_REFRESH_TIME_IN_MEM = 0.0

@db_task_compat
async def refresh_client_balances_view(db: AsyncSession | None = None) -> None:
    """Refresh the mv_client_balances materialized view after financial mutations, debounced with a 10s lock."""
    global _LAST_REFRESH_TIME_IN_MEM
    import logging
    logger = logging.getLogger("fabouanes")

    now = time.time()
    if now - _LAST_REFRESH_TIME_IN_MEM < 10.0:
        logger.debug("Materialized view refresh debounced (in-memory lock active)")
        return
    _LAST_REFRESH_TIME_IN_MEM = now

    try:
        if db is None:
            async with get_async_sessionmaker()() as session:
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_client_balances"))
                await session.commit()
        else:
            await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_client_balances"))
        logger.info("Materialized view mv_client_balances refreshed successfully")
    except Exception as e:
        logger.debug("Could not refresh mv_client_balances: %s", e)


async def _dashboard_daily_summary(today: str, week_iso: str, db: AsyncSession) -> dict[str, float]:
    today_date = date.fromisoformat(today) if isinstance(today, str) else today
    week_iso_date = date.fromisoformat(week_iso) if isinstance(week_iso, str) else week_iso
    ts_sales = select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_date == today_date).scalar_subquery()
    ts_profit = select(func.coalesce(func.sum(Sale.profit_amount), 0)).where(Sale.sale_date == today_date).scalar_subquery()
    trs_sales = select(func.coalesce(func.sum(RawSale.total), 0)).where(RawSale.sale_date == today_date).scalar_subquery()
    trs_profit = select(func.coalesce(func.sum(RawSale.profit_amount), 0)).where(RawSale.sale_date == today_date).scalar_subquery()
    tp_cash = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.payment_date == today_date).scalar_subquery()
    ws_sales = select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_date == week_iso_date).scalar_subquery()
    wrs_sales = select(func.coalesce(func.sum(RawSale.total), 0)).where(RawSale.sale_date == week_iso_date).scalar_subquery()

    daily_query = select(
        (ts_sales + trs_sales).label("sales_today"),
        (ws_sales + wrs_sales).label("sales_week_ago"),
        tp_cash.label("cash_today"),
        (ts_profit + trs_profit).label("profit_today")
    )

    async def load():
        res = await db.execute(daily_query)
        row = res.first()
        return dict(row._mapping) if row else {}

    row = await async_cached_result(
        ("dashboard_daily_summary", today, week_iso),
        load,
        ttl_seconds=20.0,
    )
    return {key: float(row[key] if row else 0) for key in ("sales_today", "sales_week_ago", "cash_today", "profit_today")}


async def _dashboard_cumulative_summary(db: AsyncSession) -> dict[str, float]:
    total_receivables_sub = select(func.coalesce(func.sum(literal_column("balance")), 0)).select_from(text("mv_client_balances")).scalar_subquery()

    total_profit_sub = select(
        func.coalesce(select(func.sum(Sale.profit_amount)).scalar_subquery(), 0) +
        func.coalesce(select(func.sum(RawSale.profit_amount)).scalar_subquery(), 0)
    ).scalar_subquery()

    revenue_sub = select(
        func.coalesce(select(func.sum(Sale.total)).scalar_subquery(), 0) +
        func.coalesce(select(func.sum(RawSale.total)).scalar_subquery(), 0)
    ).scalar_subquery()

    raw_sale_cog_expr = case(
        (func.lower(RawSale.unit).like('sac%'), RawSale.quantity * func.coalesce(func.nullif(func.regexp_replace(RawSale.unit, '[^0-9.]', '', 'g'), '').cast(Numeric), 50)),
        (func.lower(RawSale.unit).in_(['qt', 'quintal']), RawSale.quantity * 100),
        else_=RawSale.quantity
    ) * RawSale.cost_price_snapshot

    cost_of_goods_sub = select(
        func.coalesce(select(func.sum(Sale.quantity * Sale.cost_price_snapshot)).scalar_subquery(), 0) +
        func.coalesce(select(func.sum(raw_sale_cog_expr)).scalar_subquery(), 0)
    ).scalar_subquery()

    cumulative_query = select(
        total_receivables_sub.label("total_receivables"),
        total_profit_sub.label("total_profit"),
        revenue_sub.label("revenue"),
        cost_of_goods_sub.label("cost_of_goods"),
        total_profit_sub.label("gross_profit")
    )

    async def load():
        res = await db.execute(cumulative_query)
        row = res.first()
        return dict(row._mapping) if row else {}

    row = await async_cached_result(
        ("dashboard_cumulative_summary",),
        load,
        ttl_seconds=300.0,
    )
    return {
        key: float(row[key] if row else 0)
        for key in ("total_receivables", "total_profit", "revenue", "cost_of_goods", "gross_profit")
    }


async def _build_kpis_for_date(target_date: str, db: AsyncSession) -> dict[str, float | str]:
    target_date_obj = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    s_cte = select(func.coalesce(func.sum(Sale.total), 0).label("sales_total"), func.coalesce(func.sum(Sale.profit_amount), 0).label("profit")).where(Sale.sale_date == target_date_obj).cte("s")
    rs_cte = select(func.coalesce(func.sum(RawSale.total), 0).label("sales_total"), func.coalesce(func.sum(RawSale.profit_amount), 0).label("profit")).where(RawSale.sale_date == target_date_obj).cte("rs")
    p_cte = select(func.coalesce(func.sum(Payment.amount), 0).label("cash")).where(Payment.payment_date == target_date_obj).cte("p")

    receivables_val = (
        select(func.coalesce(func.sum(Client.opening_credit), 0)).scalar_subquery() +
        select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.sale_type == 'credit', Sale.sale_date <= target_date_obj).scalar_subquery() +
        select(func.coalesce(func.sum(RawSale.total), 0)).where(RawSale.sale_type == 'credit', RawSale.sale_date <= target_date_obj).scalar_subquery() -
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.payment_type == 'versement', Payment.payment_date <= target_date_obj).scalar_subquery() +
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.payment_type == 'avance', Payment.payment_date <= target_date_obj).scalar_subquery()
    )

    kpi_query = select(
        (s_cte.c.sales_total + rs_cte.c.sales_total).label("sales"),
        p_cte.c.cash.label("cash"),
        (s_cte.c.profit + rs_cte.c.profit).label("profit"),
        receivables_val.label("receivables")
    ).select_from(s_cte.join(rs_cte, true()).join(p_cte, true()))

    res = await db.execute(kpi_query)
    row = res.first()
    return {
        "date": target_date,
        "sales": float(row._mapping["sales"] if row else 0),
        "cash": float(row._mapping["cash"] if row else 0),
        "profit": float(row._mapping["profit"] if row else 0),
        "receivables": float(row._mapping["receivables"] if row else 0),
    }


# --- Operation / Journal Queries (migrated from operation_repository) ---

async def list_recent_operations(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession | None = None,
) -> tuple[list[dict], int]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_recent_operations_impl(search, date_from, date_to, kind, page, page_size, session)
    return await _list_recent_operations_impl(search, date_from, date_to, kind, page, page_size, db)

async def _list_recent_operations_impl(
    search: str | None,
    date_from: str | None,
    date_to: str | None,
    kind: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    # finished sales
    s1 = select(
        literal_column("'sale'").label("operation_type"),
        Sale.id.label("row_id"),
        Sale.sale_date.label("event_date"),
        func.coalesce(Client.name, 'Comptoir').label("partner_name"),
        FinishedProduct.name.label("item_name"),
        Sale.notes,
        Sale.total.label("amount"),
        Sale.balance_due.label("balance_due"),
        literal_column("'Vente produit final'").label("operation_label")
    ).select_from(Sale).outerjoin(Client, Client.id == Sale.client_id).join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)

    # raw sales
    s2 = select(
        literal_column("'sale'").label("operation_type"),
        RawSale.id.label("row_id"),
        RawSale.sale_date.label("event_date"),
        func.coalesce(Client.name, 'Comptoir').label("partner_name"),
        RawMaterial.name.label("item_name"),
        RawSale.notes,
        RawSale.total.label("amount"),
        RawSale.balance_due.label("balance_due"),
        literal_column("'Vente matiere premiere'").label("operation_label")
    ).select_from(RawSale).outerjoin(Client, Client.id == RawSale.client_id).join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)

    # payments
    s3 = select(
        literal_column("'payment'").label("operation_type"),
        Payment.id.label("row_id"),
        Payment.payment_date.label("event_date"),
        Client.name.label("partner_name"),
        case((Payment.payment_type == 'avance', 'Avance client'), else_='Versement client').label("item_name"),
        Payment.notes,
        Payment.amount.label("amount"),
        literal_column("0").label("balance_due"),
        case((Payment.payment_type == 'avance', 'Avance'), else_='Versement').label("operation_label")
    ).select_from(Payment).join(Client, Client.id == Payment.client_id)

    # purchases
    s4 = select(
        literal_column("'purchase'").label("operation_type"),
        Purchase.id.label("row_id"),
        Purchase.purchase_date.label("event_date"),
        func.coalesce(Supplier.name, 'Sans fournisseur').label("partner_name"),
        RawMaterial.name.label("item_name"),
        Purchase.notes,
        Purchase.total.label("amount"),
        literal_column("0").label("balance_due"),
        literal_column("'Achat'").label("operation_label")
    ).select_from(Purchase).outerjoin(Supplier, Supplier.id == Purchase.supplier_id).join(RawMaterial, RawMaterial.id == Purchase.raw_material_id)

    # productions
    s5 = select(
        literal_column("'production'").label("operation_type"),
        ProductionBatch.id.label("row_id"),
        ProductionBatch.production_date.label("event_date"),
        literal_column("''").label("partner_name"),
        FinishedProduct.name.label("item_name"),
        ProductionBatch.notes,
        ProductionBatch.production_cost.label("amount"),
        literal_column("0").label("balance_due"),
        literal_column("'Production'").label("operation_label")
    ).select_from(ProductionBatch).join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id)

    # Combine using union_all
    union_stmt = union_all(s1, s2, s3, s4, s5).subquery("x")

    stmt = select(union_stmt)
    if search:
        search_pat = f"%{search}%"
        stmt = stmt.where(
            func.lower(
                func.coalesce(union_stmt.c.partner_name, '') + ' ' +
                func.coalesce(union_stmt.c.item_name, '') + ' ' +
                func.coalesce(union_stmt.c.notes, '') + ' ' +
                func.coalesce(union_stmt.c.operation_label, '')
            ).like(search_pat.lower())
        )

    if date_from:
        stmt = stmt.where(union_stmt.c.event_date >= date_from)
    if date_to:
        stmt = stmt.where(union_stmt.c.event_date <= date_to)
    if kind in {"sale", "payment", "purchase", "production"}:
        stmt = stmt.where(union_stmt.c.operation_type == kind)

    stmt = stmt.add_columns(func.count().over().label("_total_count"))

    # Order by event_date desc, row_id desc
    stmt = stmt.order_by(union_stmt.c.event_date.desc(), union_stmt.c.row_id.desc()).offset((page - 1) * page_size).limit(page_size)

    res = await db.execute(stmt)
    rows = [dict(row._mapping) for row in res.fetchall()]
    total = int(rows[0]["_total_count"]) if rows else 0
    return rows, total
