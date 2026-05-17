"""Requêtes SQL d'agrégation pour les rapports et statistiques."""
from __future__ import annotations

from datetime import date, timedelta

from app.core.db_access import query_db


# ── Ventes par mois ──

def sales_by_month(months: int = 12) -> list[dict]:
    rows = query_db(
        """
        SELECT month, SUM(total_sales) AS total, SUM(total_profit) AS profit,
               SUM(nb_sales) AS count
        FROM (
            SELECT substr(sale_date, 1, 7) AS month,
                   SUM(total) AS total_sales, SUM(profit_amount) AS total_profit,
                   COUNT(*) AS nb_sales
            FROM sales GROUP BY substr(sale_date, 1, 7)
            UNION ALL
            SELECT substr(sale_date, 1, 7) AS month,
                   SUM(total) AS total_sales, SUM(profit_amount) AS total_profit,
                   COUNT(*) AS nb_sales
            FROM raw_sales GROUP BY substr(sale_date, 1, 7)
        ) x
        GROUP BY month ORDER BY month DESC LIMIT ?
        """,
        (months,),
    )
    return [dict(r) for r in rows]


# ── Achats par mois ──

def purchases_by_month(months: int = 12) -> list[dict]:
    rows = query_db(
        """
        SELECT substr(purchase_date, 1, 7) AS month,
               SUM(total) AS total, COUNT(*) AS count
        FROM purchases
        GROUP BY substr(purchase_date, 1, 7)
        ORDER BY month DESC LIMIT ?
        """,
        (months,),
    )
    return [dict(r) for r in rows]


# ── Top produits par CA ──

def top_products_by_revenue(limit: int = 10, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    where_f = "WHERE 1=1"
    where_r = "WHERE 1=1"
    params: list = []
    if date_from:
        where_f += " AND s.sale_date >= ?"
        where_r += " AND rs.sale_date >= ?"
        params.extend([date_from, date_from])
    if date_to:
        where_f += " AND s.sale_date <= ?"
        where_r += " AND rs.sale_date <= ?"
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
        GROUP BY 1 ORDER BY revenue DESC LIMIT ?
        """,
        tuple(params),
    )
    return [dict(r) for r in rows]


# ── Top clients par CA ──

def top_clients_by_revenue(limit: int = 10, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    where_f = "WHERE s.client_id IS NOT NULL"
    where_r = "WHERE rs.client_id IS NOT NULL"
    params: list = []
    if date_from:
        where_f += " AND s.sale_date >= ?"
        where_r += " AND rs.sale_date >= ?"
        params.extend([date_from, date_from])
    if date_to:
        where_f += " AND s.sale_date <= ?"
        where_r += " AND rs.sale_date <= ?"
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
        GROUP BY 1 ORDER BY revenue DESC LIMIT ?
        """,
        tuple(params),
    )
    return [dict(r) for r in rows]


# ── Résumé global sur une période ──

def period_summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    where_s = "WHERE 1=1"
    where_p = "WHERE 1=1"
    where_pay = "WHERE 1=1"
    params_s: list = []
    params_p: list = []
    params_pay: list = []
    if date_from:
        where_s += " AND sale_date >= ?"
        where_p += " AND purchase_date >= ?"
        where_pay += " AND payment_date >= ?"
        params_s.append(date_from)
        params_p.append(date_from)
        params_pay.append(date_from)
    if date_to:
        where_s += " AND sale_date <= ?"
        where_p += " AND purchase_date <= ?"
        where_pay += " AND payment_date <= ?"
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


# ── Ventes par jour (pour graphique détaillé) ──

def daily_sales(days: int = 30) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = query_db(
        """
        SELECT day, SUM(total) AS total, SUM(profit) AS profit, SUM(nb) AS count
        FROM (
            SELECT sale_date AS day, SUM(total) AS total, SUM(profit_amount) AS profit, COUNT(*) AS nb
            FROM sales WHERE sale_date >= ? GROUP BY sale_date
            UNION ALL
            SELECT sale_date AS day, SUM(total) AS total, SUM(profit_amount) AS profit, COUNT(*) AS nb
            FROM raw_sales WHERE sale_date >= ? GROUP BY sale_date
        ) x
        GROUP BY day ORDER BY day ASC
        """,
        (cutoff, cutoff),
    )
    return [dict(r) for r in rows]


# ── Dépenses par mois (si le module dépenses est chargé) ──

def expenses_by_month_safe(months: int = 12) -> list[dict]:
    """Retourne les dépenses par mois, ou une liste vide si la table n'existe pas."""
    try:
        rows = query_db(
            """SELECT substr(date, 1, 7) AS month,
                      COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
               FROM expenses
               GROUP BY substr(date, 1, 7)
               ORDER BY month DESC LIMIT ?""",
            (months,),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def expenses_total_safe(date_from: str | None = None, date_to: str | None = None) -> float:
    """Total dépenses sur une période, 0 si la table n'existe pas."""
    try:
        sql = "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE 1=1"
        params: list = []
        if date_from:
            sql += " AND date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND date <= ?"
            params.append(date_to)
        row = query_db(sql, tuple(params), one=True)
        return float(row["total"]) if row else 0.0
    except Exception:
        return 0.0
