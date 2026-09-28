"""Requêtes ORM d'agrégation et accès aux données pour le module Rapports."""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Numeric, String, case, cast, func, literal_column, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    Client,
    Expense,
    FinishedProduct,
    Payment,
    Purchase,
    RawMaterial,
    RawSale,
    Sale,
)
from app.modules.reports.dashboard_repo import (
    _build_dashboard_snapshot,
    _build_debt_by_client,
    _build_kpi_history,
    _build_kpis_for_date,
    _build_kpis_for_period,
    _build_stock_materials,
    _dashboard_cumulative_summary,
    _dashboard_daily_summary,
    _list_recent_operations_impl,
    get_dashboard_snapshot,
    get_kpi_history_last_30_days,
    get_kpis_for_date,
    get_kpis_for_period,
    list_recent_operations,
    refresh_client_balances_view,
)


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _scalar_value(self, stmt: Any, default: Any = 0) -> Any:
        if hasattr(self.session, "scalar") and callable(getattr(self.session, "scalar", None)):
            res = self.session.scalar(stmt)
            val = await res if inspect.isawaitable(res) else res
            return val if val is not None else default
        res = await self.session.execute(stmt)
        if hasattr(res, "scalar") and callable(getattr(res, "scalar", None)):
            val = res.scalar()
            return val if val is not None else default
        if hasattr(res, "scalar_one") and callable(getattr(res, "scalar_one", None)):
            try:
                return res.scalar_one()
            except Exception:
                return default
        return default

    async def get_sales_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        subq1 = select(
            func.substr(cast(Sale.sale_date, String), 1, 7).label("month"),
            func.sum(Sale.total).label("total_sales"),
            func.sum(Sale.profit_amount).label("total_profit"),
            func.count().label("nb_sales"),
        ).group_by(literal_column("month"))

        subq2 = select(
            func.substr(cast(RawSale.sale_date, String), 1, 7).label("month"),
            func.sum(RawSale.total).label("total_sales"),
            func.sum(RawSale.profit_amount).label("total_profit"),
            func.count().label("nb_sales"),
        ).group_by(literal_column("month"))

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = (
            select(
                union_stmt.c.month,
                func.sum(union_stmt.c.total_sales).label("total"),
                func.sum(union_stmt.c.total_profit).label("profit"),
                func.sum(union_stmt.c.nb_sales).label("count"),
            )
            .group_by(union_stmt.c.month)
            .order_by(union_stmt.c.month.desc())
            .limit(months)
        )

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_purchases_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        stmt = (
            select(
                func.substr(cast(Purchase.purchase_date, String), 1, 7).label("month"),
                func.sum(Purchase.total).label("total"),
                func.count().label("count"),
            )
            .group_by(literal_column("month"))
            .order_by(literal_column("month").desc())
            .limit(months)
        )

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_top_products_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # Finished products subquery
        stmt_f = (
            select(
                FinishedProduct.name.label("name"),
                func.sum(Sale.total).label("revenue"),
                func.sum(Sale.profit_amount).label("profit"),
                func.sum(Sale.quantity).label("qty"),
            )
            .select_from(Sale)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
        )

        if date_from_val:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from_val)
        if date_to_val:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to_val)
        stmt_f = stmt_f.group_by(FinishedProduct.name)

        # Raw materials subquery
        stmt_r = (
            select(
                func.coalesce(func.nullif(RawSale.custom_item_name, ""), RawMaterial.name).label("name"),
                func.sum(RawSale.total).label("revenue"),
                func.sum(RawSale.profit_amount).label("profit"),
                func.sum(RawSale.quantity).label("qty"),
            )
            .select_from(RawSale)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
        )

        if date_from_val:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to_val)
        stmt_r = stmt_r.group_by(RawSale.custom_item_name, RawMaterial.name)

        union_stmt = union_all(stmt_f, stmt_r).subquery()

        stmt = (
            select(
                union_stmt.c.name,
                func.sum(union_stmt.c.revenue).label("revenue"),
                func.sum(union_stmt.c.profit).label("profit"),
                func.sum(union_stmt.c.qty).label("qty"),
            )
            .group_by(union_stmt.c.name)
            .order_by(literal_column("revenue").desc())
            .limit(limit)
        )

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_top_clients_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        date_from_val = date.fromisoformat(date_from) if isinstance(date_from, str) else date_from
        date_to_val = date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
        # Finished sales subquery
        stmt_f = (
            select(
                Client.name.label("name"),
                func.sum(Sale.total).label("revenue"),
                func.sum(Sale.profit_amount).label("profit"),
                func.count().label("nb"),
            )
            .select_from(Sale)
            .join(Client, Client.id == Sale.client_id)
            .where(Sale.client_id.is_not(None))
        )

        if date_from_val:
            stmt_f = stmt_f.where(Sale.sale_date >= date_from_val)
        if date_to_val:
            stmt_f = stmt_f.where(Sale.sale_date <= date_to_val)
        stmt_f = stmt_f.group_by(Client.name)

        # Raw sales subquery
        stmt_r = (
            select(
                Client.name.label("name"),
                func.sum(RawSale.total).label("revenue"),
                func.sum(RawSale.profit_amount).label("profit"),
                func.count().label("nb"),
            )
            .select_from(RawSale)
            .join(Client, Client.id == RawSale.client_id)
            .where(RawSale.client_id.is_not(None))
        )

        if date_from_val:
            stmt_r = stmt_r.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_r = stmt_r.where(RawSale.sale_date <= date_to_val)
        stmt_r = stmt_r.group_by(Client.name)

        union_stmt = union_all(stmt_f, stmt_r).subquery()

        stmt = (
            select(
                union_stmt.c.name,
                func.sum(union_stmt.c.revenue).label("revenue"),
                func.sum(union_stmt.c.profit).label("profit"),
                func.sum(union_stmt.c.nb).label("count"),
            )
            .group_by(union_stmt.c.name)
            .order_by(literal_column("revenue").desc())
            .limit(limit)
        )

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

        total_sales = (await self._scalar_value(stmt_s_total)) + (await self._scalar_value(stmt_rs_total))
        total_profit = (await self._scalar_value(stmt_s_profit)) + (await self._scalar_value(stmt_rs_profit))
        nb_sales = (await self._scalar_value(stmt_s_count)) + (await self._scalar_value(stmt_rs_count))
        total_purchases = await self._scalar_value(stmt_p_total)
        nb_purchases = await self._scalar_value(stmt_p_count)
        total_payments = await self._scalar_value(stmt_pay_total)
        nb_payments = await self._scalar_value(stmt_pay_count)

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
        subq1 = (
            select(
                Sale.sale_date.label("day"),
                func.sum(Sale.total).label("total"),
                func.sum(Sale.profit_amount).label("profit"),
                func.count().label("nb"),
            )
            .where(Sale.sale_date >= cutoff)
            .group_by(Sale.sale_date)
        )

        subq2 = (
            select(
                RawSale.sale_date.label("day"),
                func.sum(RawSale.total).label("total"),
                func.sum(RawSale.profit_amount).label("profit"),
                func.count().label("nb"),
            )
            .where(RawSale.sale_date >= cutoff)
            .group_by(RawSale.sale_date)
        )

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = (
            select(
                union_stmt.c.day,
                func.sum(union_stmt.c.total).label("total"),
                func.sum(union_stmt.c.profit).label("profit"),
                func.sum(union_stmt.c.nb).label("count"),
            )
            .group_by(union_stmt.c.day)
            .order_by(union_stmt.c.day.asc())
        )

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_expenses_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        try:
            stmt = (
                select(
                    func.substr(cast(Expense.date, String), 1, 7).label("month"),
                    func.coalesce(func.sum(Expense.amount), 0).label("total"),
                    func.count().label("count"),
                )
                .group_by(literal_column("month"))
                .order_by(literal_column("month").desc())
                .limit(months)
            )

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

            return float(await self._scalar_value(stmt, 0.0))
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
        extracted_num = func.nullif(func.regexp_replace(RawSale.unit, "[^0-9.]", "", "g"), "")
        sac_multiplier = cast(func.coalesce(extracted_num, "50"), Numeric)

        case_expr = case(
            (unit_lower.like("sac%"), RawSale.quantity * sac_multiplier),
            (unit_lower.in_(["qt", "quintal"]), RawSale.quantity * 100),
            else_=RawSale.quantity,
        )

        stmt_rs = select(func.coalesce(func.sum(case_expr * RawSale.cost_price_snapshot), 0))
        if date_from_val:
            stmt_rs = stmt_rs.where(RawSale.sale_date >= date_from_val)
        if date_to_val:
            stmt_rs = stmt_rs.where(RawSale.sale_date <= date_to_val)

        cogs_sales = await self._scalar_value(stmt_s)
        cogs_raw = await self._scalar_value(stmt_rs)

        return float(cogs_sales + cogs_raw)

    async def get_expenses_by_category(self) -> list[dict[str, Any]]:
        try:
            stmt = (
                select(Expense.category, func.sum(Expense.amount).label("total"), func.count().label("count"))
                .group_by(Expense.category)
                .order_by(literal_column("total").desc())
            )

            res = await self.session.execute(stmt)
            return [dict(row) for row in res.mappings().all()]
        except Exception:
            return []

    async def get_clients(self) -> list[dict[str, Any]]:
        stmt = select(Client.id, Client.name, Client.notes, Client.opening_credit)
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_credit_sales(self) -> list[dict[str, Any]]:
        subq1 = select(Sale.client_id, Sale.sale_date.label("date"), Sale.total).where(
            Sale.client_id.is_not(None), Sale.sale_type == "credit"
        )

        subq2 = select(RawSale.client_id, RawSale.sale_date.label("date"), RawSale.total).where(
            RawSale.client_id.is_not(None), RawSale.sale_type == "credit"
        )

        union_stmt = union_all(subq1, subq2).subquery()

        stmt = select(union_stmt).order_by(union_stmt.c.date.desc())
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_payments(self) -> list[dict[str, Any]]:
        stmt = (
            select(Payment.client_id, Payment.payment_date.label("date"), Payment.amount, Payment.payment_type)
            .where(Payment.client_id.is_not(None))
            .order_by(literal_column("date").asc())
        )

        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_livre_journal_entries(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Extrait toutes les écritures pour le Livre Journal ordonnées chronologiquement."""
        stmt_sales = select(
            Sale.sale_date.label("tx_date"),
            func.concat("Vente #", cast(Sale.id, String)).label("tx_ref"),
            func.concat("Vente client ID ", cast(Sale.client_id, String)).label("label"),
            func.coalesce(Sale.total, 0.0).label("debit"),
            literal_column("0.0").label("credit"),
        )
        stmt_purchases = select(
            Purchase.purchase_date.label("tx_date"),
            func.concat("Achat #", cast(Purchase.id, String)).label("tx_ref"),
            func.concat("Achat fourn. ID ", cast(func.coalesce(Purchase.supplier_id, 0), String)).label("label"),
            literal_column("0.0").label("debit"),
            func.coalesce(Purchase.total, 0.0).label("credit"),
        )
        stmt_payments = select(
            Payment.payment_date.label("tx_date"),
            func.concat("Versement #", cast(Payment.id, String)).label("tx_ref"),
            func.concat("Règlement client ID ", cast(Payment.client_id, String)).label("label"),
            literal_column("0.0").label("debit"),
            func.coalesce(Payment.amount, 0.0).label("credit"),
        )
        stmt_expenses = select(
            Expense.date.label("tx_date"),
            func.concat("Dépense #", cast(Expense.id, String)).label("tx_ref"),
            func.concat(func.coalesce(Expense.category, "Autre"), " : ", func.coalesce(Expense.description, "")).label(
                "label"
            ),
            literal_column("0.0").label("debit"),
            func.coalesce(Expense.amount, 0.0).label("credit"),
        )
        u = union_all(stmt_sales, stmt_purchases, stmt_payments, stmt_expenses).subquery()
        stmt = (
            select(u.c.tx_date, u.c.tx_ref, u.c.label, u.c.debit, u.c.credit)
            .order_by(u.c.tx_date.desc(), u.c.tx_ref.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]

    async def get_marge_brute_data(self) -> list[dict[str, Any]]:
        """Agrège les ventes par produit fini pour l'analyse de marge brute."""
        stmt = (
            select(
                FinishedProduct.name,
                func.coalesce(func.sum(Sale.quantity), 0.0).label("total_qty"),
                func.coalesce(func.sum(Sale.total), 0.0).label("total_revenue"),
                cast(FinishedProduct.avg_cost, Numeric).label("avg_cost"),
            )
            .select_from(FinishedProduct)
            .outerjoin(Sale, Sale.finished_product_id == FinishedProduct.id)
            .group_by(FinishedProduct.id, FinishedProduct.name, FinishedProduct.avg_cost)
            .order_by(func.coalesce(func.sum(Sale.total), 0.0).desc())
        )
        res = await self.session.execute(stmt)
        return [dict(row) for row in res.mappings().all()]




__all__ = [
    "ReportsRepository",
    "get_dashboard_snapshot",
    "get_kpis_for_date",
    "get_kpis_for_period",
    "get_kpi_history_last_30_days",
    "list_recent_operations",
    "refresh_client_balances_view",
    "_build_dashboard_snapshot",
    "_build_stock_materials",
    "_build_debt_by_client",
    "_dashboard_daily_summary",
    "_dashboard_cumulative_summary",
    "_build_kpis_for_date",
    "_list_recent_operations_impl",
    "_build_kpis_for_period",
    "_build_kpi_history",
]
