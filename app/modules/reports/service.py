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
    """Construit toutes les données nécessaires pour la page de rapports."""
    summary = period_summary(date_from, date_to)
    expenses_total = expenses_total_safe(date_from, date_to)

    # Bénéfice net = profit brut - dépenses
    net_profit = summary["total_profit"] - expenses_total

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
        "net_profit": net_profit,
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
