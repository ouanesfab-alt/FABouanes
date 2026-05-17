"""Logique métier du module Rapports — préparation des données pour les graphiques."""
from __future__ import annotations

from app.modules.reports.repository import (
    daily_sales,
    expenses_by_month_safe,
    expenses_total_safe,
    period_summary,
    purchases_by_month,
    sales_by_month,
    top_clients_by_revenue,
    top_products_by_revenue,
)


def build_reports_context(date_from: str | None = None, date_to: str | None = None) -> dict:
    """Construit toutes les données nécessaires pour la page de rapports, y compris les analyses BI."""
    from datetime import date, timedelta
    import re
    
    summary = period_summary(date_from, date_to)
    expenses_total = expenses_total_safe(date_from, date_to)

    # ── CALCUL DES COMPOSANTS DE RENTABILITÉ NETTE (COGS, MARGE NETTE) ──
    # COGS (Coût des marchandises vendues) pour la période
    where_s = "WHERE 1=1"
    where_rs = "WHERE 1=1"
    params_cogs = []
    if date_from:
        where_s += " AND sale_date >= ?"
        where_rs += " AND sale_date >= ?"
        params_cogs.extend([date_from, date_from])
    if date_to:
        where_s += " AND sale_date <= ?"
        where_rs += " AND sale_date <= ?"
        params_cogs.extend([date_to, date_to])
        
    cogs_row = query_db(
        f"""
        SELECT
            COALESCE((SELECT SUM(quantity * cost_price_snapshot) FROM sales {where_s}), 0)
            + COALESCE((
                SELECT SUM(
                    (CASE
                        WHEN lower(unit) = 'sac' THEN quantity * 50
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
    cogs = float(cogs_row["cost_of_goods"]) if cogs_row else 0.0
    
    # Marge Brute BI
    revenue = summary["total_sales"]
    gross_margin = revenue - cogs
    net_profit = gross_margin - expenses_total
    
    net_margin_pct = round((net_profit / revenue) * 100, 1) if revenue > 0 else 0.0
    gross_margin_pct = round((gross_margin / revenue) * 100, 1) if revenue > 0 else 0.0

    # Dépenses par catégorie
    expenses_by_cat_rows = query_db(
        """
        SELECT category, SUM(amount) AS total, COUNT(*) AS count
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
        """
    )
    expenses_by_cat = [dict(e) for e in expenses_by_cat_rows]

    # ── RAPPORT ANGLAIS/FRANÇAIS SUR L'ÂGE DES DETTES & RETARD DE PAIEMENT CLIENTS ──
    clients = query_db("SELECT id, name, notes, opening_credit FROM clients")
    sales = query_db(
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
    payments = query_db(
        """
        SELECT client_id, payment_date AS date, amount, payment_type
        FROM payments
        WHERE client_id IS NOT NULL
        ORDER BY date ASC
        """
    )

    client_debts = []
    total_under_30 = 0.0
    total_30_to_90 = 0.0
    total_over_90 = 0.0
    total_outstanding = 0.0
    
    for client in clients:
        c_sales = [s for s in sales if s["client_id"] == client["id"]]
        c_payments = [p for p in payments if p["client_id"] == client["id"]]
        
        total_credit = float(client["opening_credit"]) + sum(float(s["total"]) for s in c_sales)
        total_paid_versements = sum(float(p["amount"]) for p in c_payments if p["payment_type"] == "versement")
        total_paid_avances = sum(float(p["amount"]) for p in c_payments if p["payment_type"] == "avance")
        
        current_debt = total_credit - total_paid_versements + total_paid_avances
        
        if current_debt > 0.01:
            # Brackets
            brackets = {"under_30": 0.0, "30_to_90": 0.0, "over_90": 0.0}
            rem = current_debt
            today = date.today()
            c_sales_desc = sorted(c_sales, key=lambda x: x["date"], reverse=True)
            for s in c_sales_desc:
                if rem <= 0:
                    break
                unpaid = min(rem, float(s["total"]))
                sale_day = date.fromisoformat(s["date"])
                days = (today - sale_day).days
                if days < 30:
                    brackets["under_30"] += unpaid
                elif days <= 90:
                    brackets["30_to_90"] += unpaid
                else:
                    brackets["over_90"] += unpaid
                rem -= unpaid
            if rem > 0:
                brackets["over_90"] += rem
                
            # Repayment delay FIFO
            sales_fifo = []
            if float(client["opening_credit"]) > 0:
                sales_fifo.append({"date": "2020-01-01", "total": float(client["opening_credit"])})
            for s in sorted(c_sales, key=lambda x: x["date"]):
                sales_fifo.append({"date": s["date"], "total": float(s["total"])})
                
            c_versements = sorted([p for p in c_payments if p["payment_type"] == "versement"], key=lambda x: x["date"])
            delays = []
            sale_idx = 0
            num_sales = len(sales_fifo)
            for p in c_versements:
                p_amount = float(p["amount"])
                p_date = date.fromisoformat(p["date"])
                while p_amount > 0 and sale_idx < num_sales:
                    sale = sales_fifo[sale_idx]
                    s_total = sale["total"]
                    s_date = date.fromisoformat(sale["date"]) if sale["date"] != "2020-01-01" else None
                    
                    if s_total <= 0:
                        sale_idx += 1
                        continue
                        
                    payment_applied = min(p_amount, s_total)
                    p_amount -= payment_applied
                    sale["total"] -= payment_applied
                    
                    if s_date:
                       delay_days = (p_date - s_date).days
                       if delay_days >= 0:
                           delays.append(delay_days)
                           
                    if sale["total"] <= 0:
                        sale_idx += 1
            avg_delay = round(sum(delays) / len(delays), 1) if delays else None
            
            # Limit check
            limit = 200000.0
            notes_str = str(client["notes"] or "")
            match = re.search(r"(?i)limite\s*:\s*([\d\s]+)", notes_str)
            if match:
                try:
                    limit = float(re.sub(r"[^\d]", "", match.group(1)))
                except Exception:
                    pass
            limit_utilized_pct = round((current_debt / limit) * 100, 1)
            limit_exceeded = current_debt > limit
            
            client_debts.append({
                "id": client["id"],
                "name": client["name"],
                "debt": current_debt,
                "under_30": brackets["under_30"],
                "30_to_90": brackets["30_to_90"],
                "over_90": brackets["over_90"],
                "avg_delay": avg_delay,
                "limit": limit,
                "limit_utilized_pct": limit_utilized_pct,
                "limit_exceeded": limit_exceeded,
            })
            
            total_under_30 += brackets["under_30"]
            total_30_to_90 += brackets["30_to_90"]
            total_over_90 += brackets["over_90"]
            total_outstanding += current_debt

    client_debts = sorted(client_debts, key=lambda x: x["debt"], reverse=True)
    debt_totals = {
        "under_30": total_under_30,
        "30_to_90": total_30_to_90,
        "over_90": total_over_90,
        "outstanding": total_outstanding,
    }

    # Tendances mensuelles (12 derniers mois)
    monthly_sales = sales_by_month(12)
    monthly_purchases = purchases_by_month(12)
    monthly_expenses = expenses_by_month_safe(12)

    # Fusionner les mois pour les graphiques
    all_months = sorted(set(
        [r["month"] for r in monthly_sales]
        + [r["month"] for r in monthly_purchases]
        + [r["month"] for r in monthly_expenses]
    ))
    sales_map = {r["month"]: r for r in monthly_sales}
    purchases_map = {r["month"]: r for r in monthly_purchases}
    expenses_map = {r["month"]: r for r in monthly_expenses}

    chart_months = all_months[-12:] if len(all_months) > 12 else all_months
    chart_sales = [float(sales_map.get(m, {}).get("total", 0)) for m in chart_months]
    chart_profit = [float(sales_map.get(m, {}).get("profit", 0)) for m in chart_months]
    chart_purchases = [float(purchases_map.get(m, {}).get("total", 0)) for m in chart_months]
    chart_expenses = [float(expenses_map.get(m, {}).get("total", 0)) for m in chart_months]

    # Labels lisibles (2025-01 → Jan 25)
    month_names = {
        "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr", "05": "Mai", "06": "Jui",
        "07": "Jul", "08": "Aoû", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc",
    }
    chart_labels = []
    for m in chart_months:
        parts = m.split("-")
        if len(parts) == 2:
            chart_labels.append(f"{month_names.get(parts[1], parts[1])} {parts[0][2:]}")
        else:
            chart_labels.append(m)

    # Ventes quotidiennes (30 derniers jours)
    daily = daily_sales(30)
    daily_labels = [d["day"] for d in daily]
    daily_totals = [float(d["total"]) for d in daily]
    daily_profits = [float(d["profit"]) for d in daily]

    # Top produits et clients
    top_products = top_products_by_revenue(10, date_from, date_to)
    top_clients = top_clients_by_revenue(10, date_from, date_to)

    return {
        "summary": summary,
        "expenses_total": expenses_total,
        "cogs": cogs,
        "gross_margin": gross_margin,
        "net_profit": net_profit,
        "net_margin_pct": net_margin_pct,
        "gross_margin_pct": gross_margin_pct,
        "expenses_by_cat": expenses_by_cat,
        "client_debts": client_debts,
        "debt_totals": debt_totals,
        "chart_labels": chart_labels,
        "chart_sales": chart_sales,
        "chart_profit": chart_profit,
        "chart_purchases": chart_purchases,
        "chart_expenses": chart_expenses,
        "daily_labels": daily_labels,
        "daily_totals": daily_totals,
        "daily_profits": daily_profits,
        "top_products": top_products,
        "top_clients": top_clients,
        "date_from": date_from or "",
        "date_to": date_to or "",
    }
