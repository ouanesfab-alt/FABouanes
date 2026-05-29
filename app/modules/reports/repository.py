"""Requêtes SQL d'agrégation et accès aux données pour le module Rapports."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from app.core.db_access import query_db

class ReportsRepository:
    def get_sales_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        rows = query_db(
            """
            SELECT month, SUM(total_sales) AS total, SUM(total_profit) AS profit,
                   SUM(nb_sales) AS count
            FROM (
                SELECT substr(sale_date::text, 1, 7) AS month,
                       SUM(total) AS total_sales, SUM(profit_amount) AS total_profit,
                       COUNT(*) AS nb_sales
                FROM sales GROUP BY substr(sale_date::text, 1, 7)
                UNION ALL
                SELECT substr(sale_date::text, 1, 7) AS month,
                       SUM(total) AS total_sales, SUM(profit_amount) AS total_profit,
                       COUNT(*) AS nb_sales
                FROM raw_sales GROUP BY substr(sale_date::text, 1, 7)
            ) x
            GROUP BY month ORDER BY month DESC LIMIT %s
            """,
            (months,),
        )
        return [dict(r) for r in rows]

    def get_purchases_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        rows = query_db(
            """
            SELECT substr(purchase_date::text, 1, 7) AS month,
                   SUM(total) AS total, COUNT(*) AS count
            FROM purchases
            GROUP BY substr(purchase_date::text, 1, 7)
            ORDER BY month DESC LIMIT %s
            """,
            (months,),
        )
        return [dict(r) for r in rows]

    def get_top_products_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        where_f = "WHERE 1=1"
        where_r = "WHERE 1=1"
        params: list = []
        if date_from:
            where_f += " AND s.sale_date >= %s"
            where_r += " AND rs.sale_date >= %s"
            params.extend([date_from, date_from])
        if date_to:
            where_f += " AND s.sale_date <= %s"
            where_r += " AND rs.sale_date <= %s"
            params.extend([date_to, date_to])
        params.append(limit)
        rows = query_db(
            f"""
            SELECT name, SUM(revenue) AS revenue, SUM(profit) AS profit, SUM(qty) AS qty
            FROM (
                SELECT f.name, SUM(s.total) AS revenue, SUM(s.profit_amount) AS profit, SUM(s.quantity) AS qty
                FROM sales s JOIN finished_products f ON f.id = s.finished_product_id
                {where_f} GROUP BY 1
                UNION ALL
                SELECT COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS name,
                       SUM(rs.total) AS revenue, SUM(rs.profit_amount) AS profit, SUM(rs.quantity) AS qty
                FROM raw_sales rs JOIN raw_materials r ON r.id = rs.raw_material_id
                {where_r} GROUP BY 1
            ) x
            GROUP BY 1 ORDER BY revenue DESC LIMIT %s
            """,
            tuple(params),
        )
        return [dict(r) for r in rows]

    def get_top_clients_by_revenue(
        self, limit: int = 10, date_from: str | None = None, date_to: str | None = None
    ) -> list[dict[str, Any]]:
        where_f = "WHERE s.client_id IS NOT NULL"
        where_r = "WHERE rs.client_id IS NOT NULL"
        params: list = []
        if date_from:
            where_f += " AND s.sale_date >= %s"
            where_r += " AND rs.sale_date >= %s"
            params.extend([date_from, date_from])
        if date_to:
            where_f += " AND s.sale_date <= %s"
            where_r += " AND rs.sale_date <= %s"
            params.extend([date_to, date_to])
        params.append(limit)
        rows = query_db(
            f"""
            SELECT name, SUM(revenue) AS revenue, SUM(profit) AS profit, SUM(nb) AS count
            FROM (
                SELECT c.name, SUM(s.total) AS revenue, SUM(s.profit_amount) AS profit, COUNT(*) AS nb
                FROM sales s JOIN clients c ON c.id = s.client_id
                {where_f} GROUP BY 1
                UNION ALL
                SELECT c.name, SUM(rs.total) AS revenue, SUM(rs.profit_amount) AS profit, COUNT(*) AS nb
                FROM raw_sales rs JOIN clients c ON c.id = rs.client_id
                {where_r} GROUP BY 1
            ) x
            GROUP BY 1 ORDER BY revenue DESC LIMIT %s
            """,
            tuple(params),
        )
        return [dict(r) for r in rows]

    def get_period_summary(self, date_from: str | None = None, date_to: str | None = None) -> dict[str, float]:
        where_s = "WHERE 1=1"
        where_p = "WHERE 1=1"
        where_pay = "WHERE 1=1"
        params_s: list = []
        params_p: list = []
        params_pay: list = []
        if date_from:
            where_s += " AND sale_date >= %s"
            where_p += " AND purchase_date >= %s"
            where_pay += " AND payment_date >= %s"
            params_s.append(date_from)
            params_p.append(date_from)
            params_pay.append(date_from)
        if date_to:
            where_s += " AND sale_date <= %s"
            where_p += " AND purchase_date <= %s"
            where_pay += " AND payment_date <= %s"
            params_s.append(date_to)
            params_p.append(date_to)
            params_pay.append(date_to)

        row = query_db(
            f"""
            SELECT
                COALESCE((SELECT SUM(total) FROM sales {where_s}), 0)
                + COALESCE((SELECT SUM(total) FROM raw_sales {where_s}), 0) AS total_sales,
                COALESCE((SELECT SUM(profit_amount) FROM sales {where_s}), 0)
                + COALESCE((SELECT SUM(profit_amount) FROM raw_sales {where_s}), 0) AS total_profit,
                COALESCE((SELECT COUNT(*) FROM sales {where_s}), 0)
                + COALESCE((SELECT COUNT(*) FROM raw_sales {where_s}), 0) AS nb_sales,
                COALESCE((SELECT SUM(total) FROM purchases {where_p}), 0) AS total_purchases,
                COALESCE((SELECT COUNT(*) FROM purchases {where_p}), 0) AS nb_purchases,
                COALESCE((SELECT SUM(amount) FROM payments {where_pay}), 0) AS total_payments,
                COALESCE((SELECT COUNT(*) FROM payments {where_pay}), 0) AS nb_payments
            """,
            tuple(params_s + params_s + params_s + params_s + params_s + params_s + params_p + params_p + params_pay + params_pay),
            one=True,
        )
        return {key: float(row[key]) if row else 0.0 for key in (
            "total_sales", "total_profit", "nb_sales",
            "total_purchases", "nb_purchases",
            "total_payments", "nb_payments",
        )}

    def get_daily_sales(self, days: int = 30) -> list[dict[str, Any]]:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = query_db(
            """
            SELECT day, SUM(total) AS total, SUM(profit) AS profit, SUM(nb) AS count
            FROM (
                SELECT sale_date AS day, SUM(total) AS total, SUM(profit_amount) AS profit, COUNT(*) AS nb
                FROM sales WHERE sale_date >= %s GROUP BY sale_date
                UNION ALL
                SELECT sale_date AS day, SUM(total) AS total, SUM(profit_amount) AS profit, COUNT(*) AS nb
                FROM raw_sales WHERE sale_date >= %s GROUP BY sale_date
            ) x
            GROUP BY day ORDER BY day ASC
            """,
            (cutoff, cutoff),
        )
        return [dict(r) for r in rows]

    def get_expenses_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        try:
            rows = query_db(
                """SELECT substr(date::text, 1, 7) AS month,
                          COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
                   FROM expenses
                   GROUP BY substr(date::text, 1, 7)
                   ORDER BY month DESC LIMIT %s""",
                (months,),
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_expenses_total(self, date_from: str | None = None, date_to: str | None = None) -> float:
        try:
            sql = "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE 1=1"
            params: list = []
            if date_from:
                sql += " AND date >= %s"
                params.append(date_from)
            if date_to:
                sql += " AND date <= %s"
                params.append(date_to)
            row = query_db(sql, tuple(params), one=True)
            return float(row["total"]) if row else 0.0
        except Exception:
            return 0.0

    def get_cost_of_goods(self, date_from: str | None = None, date_to: str | None = None) -> float:
        where_s = "WHERE 1=1"
        where_rs = "WHERE 1=1"
        params_cogs = []
        if date_from:
            where_s += " AND sale_date >= %s"
            where_rs += " AND sale_date >= %s"
            params_cogs.extend([date_from, date_from])
        if date_to:
            where_s += " AND sale_date <= %s"
            where_rs += " AND sale_date <= %s"
            params_cogs.extend([date_to, date_to])
            
        row = query_db(
            f"""
            SELECT
                COALESCE((SELECT SUM(quantity * cost_price_snapshot) FROM sales {where_s}), 0)
                + COALESCE((
                    SELECT SUM(
                        (CASE
                            WHEN lower(unit) LIKE 'sac%' THEN quantity * COALESCE(NULLIF(regexp_replace(unit, '[^0-9.]', '', 'g'), ''), '50')::numeric
                            WHEN lower(unit) IN ('qt', 'quintal') THEN quantity * 100
                            ELSE quantity
                        END) * cost_price_snapshot
                    )
                    FROM raw_sales {where_rs}
                 ), 0) AS cost_of_goods
            """,
            tuple(params_cogs + params_cogs),
            one=True,
        )
        return float(row["cost_of_goods"]) if row else 0.0

    def get_expenses_by_category(self) -> list[dict[str, Any]]:
        try:
            rows = query_db(
                """
                SELECT category, SUM(amount) AS total, COUNT(*) AS count
                FROM expenses
                GROUP BY category
                ORDER BY total DESC
                """
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_clients(self) -> list[dict[str, Any]]:
        rows = query_db("SELECT id, name, notes, opening_credit FROM clients")
        return [dict(r) for r in rows]

    def get_credit_sales(self) -> list[dict[str, Any]]:
        rows = query_db(
            """
            SELECT client_id, sale_date AS date, total
            FROM sales
            WHERE client_id IS NOT NULL AND sale_type = 'credit'
            UNION ALL
            SELECT client_id, sale_date AS date, total
            FROM raw_sales
            WHERE client_id IS NOT NULL AND sale_type = 'credit'
            ORDER BY date DESC
            """
        )
        return [dict(r) for r in rows]

    def get_payments(self) -> list[dict[str, Any]]:
        rows = query_db(
            """
            SELECT client_id, payment_date AS date, amount, payment_type
            FROM payments
            WHERE client_id IS NOT NULL
            ORDER BY date ASC
            """
        )
        return [dict(r) for r in rows]
