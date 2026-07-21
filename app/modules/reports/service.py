"""Service de traitement décisionnel et métier pour le module Rapports."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.repository import ReportsRepository
from app.modules.reports.dtos import (
    ReportsContextDTO,
    ReportsSummaryDTO,
    TopProductDTO,
    TopClientDTO,
    ClientDebtDTO,
    DebtTotalsDTO,
)

def _to_date(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    return val

class ReportsService:
    def __init__(self, session: AsyncSession, repository: ReportsRepository | None = None) -> None:
        self.session = session
        self.repository = repository or ReportsRepository(session)

    async def build_reports_context(self, date_from: str | None = None, date_to: str | None = None) -> ReportsContextDTO:
        """Construit toutes les données nécessaires pour la page de rapports via DTOs typés."""

        summary_raw = await self.repository.get_period_summary(date_from, date_to)
        summary = ReportsSummaryDTO(
            total_sales=Decimal(str(summary_raw.get("total_sales", 0.0))),
            total_profit=Decimal(str(summary_raw.get("total_profit", 0.0))),
            total_purchases=Decimal(str(summary_raw.get("total_purchases", 0.0))),
            total_payments=Decimal(str(summary_raw.get("total_payments", 0.0))),
            nb_sales=int(summary_raw.get("nb_sales", 0)),
            nb_purchases=int(summary_raw.get("nb_purchases", 0)),
            nb_payments=int(summary_raw.get("nb_payments", 0)),
        )

        expenses_total = Decimal(str(await self.repository.get_expenses_total(date_from, date_to)))
        cogs = Decimal(str(await self.repository.get_cost_of_goods(date_from, date_to)))

        revenue = summary.total_sales
        gross_margin = revenue - cogs
        net_profit = gross_margin - expenses_total

        # Marge en pourcentage
        net_margin_pct = round(float(net_profit / revenue) * 100.0, 1) if revenue > 0 else 0.0
        gross_margin_pct = round(float(gross_margin / revenue) * 100.0, 1) if revenue > 0 else 0.0

        # Dépenses par catégorie
        expenses_by_cat_raw = await self.repository.get_expenses_by_category()
        expenses_by_cat_labels = [str(e["category"]) for e in expenses_by_cat_raw]
        expenses_by_cat_totals = [float(e["total"]) for e in expenses_by_cat_raw]

        # ── RETARD DE PAIEMENT CLIENTS & ÂGE DES DETTES ──
        clients = await self.repository.get_clients()
        sales = await self.repository.get_credit_sales()
        payments = await self.repository.get_payments()

        sales_by_client = defaultdict(list)
        for s in sales:
            sales_by_client[s["client_id"]].append(s)

        payments_by_client = defaultdict(list)
        for p in payments:
            payments_by_client[p["client_id"]].append(p)

        client_debts: list[ClientDebtDTO] = []
        total_under_30 = Decimal("0.0")
        total_30_to_90 = Decimal("0.0")
        total_over_90 = Decimal("0.0")
        total_outstanding = Decimal("0.0")

        for client in clients:
            c_sales = sales_by_client[client["id"]]
            c_payments = payments_by_client[client["id"]]

            total_credit = Decimal(str(client["opening_credit"])) + sum(Decimal(str(s["total"])) for s in c_sales)
            total_paid_versements = sum(Decimal(str(p["amount"])) for p in c_payments if p["payment_type"] == "versement")
            total_paid_avances = sum(Decimal(str(p["amount"])) for p in c_payments if p["payment_type"] == "avance")

            current_debt = total_credit - total_paid_versements + total_paid_avances

            if current_debt > Decimal("0.01"):
                # Brackets
                brackets = {"under_30": Decimal("0.0"), "days_30_to_90": Decimal("0.0"), "over_90": Decimal("0.0")}
                rem = current_debt
                today = date.today()
                c_sales_desc = sorted(c_sales, key=lambda x: x["date"], reverse=True)
                for s in c_sales_desc:
                    if rem <= 0:
                        break
                    unpaid = min(rem, Decimal(str(s["total"])))
                    sale_day = _to_date(s["date"])
                    if sale_day:
                        age = (today - sale_day).days
                        if age < 30:
                            brackets["under_30"] += unpaid
                        elif age < 90:
                            brackets["days_30_to_90"] += unpaid
                        else:
                            brackets["over_90"] += unpaid
                    rem -= unpaid

                # Avg delay
                delays = []
                sale_idx = 0
                for p in sorted(c_payments, key=lambda x: x["date"]):
                    p_date = _to_date(p["date"])
                    if not p_date:
                        continue
                    if p["payment_type"] not in ("versement", "avance"):
                        continue
                    while sale_idx < len(c_sales_desc):
                        s_date = _to_date(c_sales_desc[sale_idx]["date"])
                        if s_date and p_date >= s_date:
                            delay_days = (p_date - s_date).days
                            if delay_days >= 0:
                                delays.append(delay_days)

                        if sale_idx < len(c_sales_desc) and c_sales_desc[sale_idx]["total"] <= 0:
                            sale_idx += 1
                        else:
                            break
                avg_delay = int(round(sum(delays) / len(delays))) if delays else None

                # Limit check
                limit = Decimal("200000.0")
                notes_str = str(client["notes"] or "")
                match = re.search(r"(?i)limite\s*:\s*([\d\s]+)", notes_str)
                if match:
                    try:
                        limit = Decimal(re.sub(r"[^\d]", "", match.group(1)))
                    except Exception:
                        pass
                limit_utilized_pct = round(float(current_debt / limit) * 100.0, 1) if limit > 0 else 0.0
                limit_utilized_pct_clamped = min(limit_utilized_pct, 100.0)
                limit_exceeded = current_debt > limit

                client_debts.append(ClientDebtDTO(
                    id=client["id"],
                    name=client["name"],
                    debt=current_debt,
                    under_30=brackets["under_30"],
                    days_30_to_90=brackets["days_30_to_90"],
                    over_90=brackets["over_90"],
                    avg_delay=avg_delay,
                    limit=limit,
                    limit_utilized_pct=limit_utilized_pct,
                    limit_utilized_pct_clamped=limit_utilized_pct_clamped,
                    limit_exceeded=limit_exceeded,
                ))

                total_under_30 += brackets["under_30"]
                total_30_to_90 += brackets["days_30_to_90"]
                total_over_90 += brackets["over_90"]
                total_outstanding += current_debt

        client_debts = sorted(client_debts, key=lambda x: x.debt, reverse=True)
        debt_totals = DebtTotalsDTO(
            under_30=total_under_30,
            days_30_to_90=total_30_to_90,
            over_90=total_over_90,
            outstanding=total_outstanding,
        )
        # Tendances mensuelles
        monthly_sales = await self.repository.get_sales_by_month(12)
        monthly_purchases = await self.repository.get_purchases_by_month(12)
        monthly_expenses = await self.repository.get_expenses_by_month(12)

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
        chart_purchases = [float(purchases_map.get(m, {}).get("total", 0)) for m in chart_months]
        chart_expenses = [float(expenses_map.get(m, {}).get("total", 0)) for m in chart_months]
        chart_profit = [s - p - e for s, p, e in zip(chart_sales, chart_purchases, chart_expenses)]

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

        # Graphique quotidien (30 jours)
        daily_sales_raw = await self.repository.get_daily_sales(30)
        daily_labels = []
        daily_totals = []
        daily_profits = []
        for r in daily_sales_raw:
            day_val = r["day"]
            if isinstance(day_val, date):
                lbl = f"{day_val.day:02d} {month_names.get(f'{day_val.month:02d}', f'{day_val.month:02d}')}"
            else:
                d_parts = str(day_val).split("-")
                if len(d_parts) >= 3:
                    lbl = f"{d_parts[2]} {month_names.get(d_parts[1], d_parts[1])}"
                else:
                    lbl = str(day_val)
            daily_labels.append(lbl)
            daily_totals.append(float(r["total"] or 0))
            daily_profits.append(float(r["profit"] or 0))

        # Top produits et clients
        top_products_raw = await self.repository.get_top_products_by_revenue(10, date_from, date_to)
        top_products = [
            TopProductDTO(
                name=p["name"],
                qty=float(p["qty"]),
                revenue=Decimal(str(p["revenue"])),
                profit=Decimal(str(p["profit"])),
            ) for p in top_products_raw
        ]

        top_clients_raw = await self.repository.get_top_clients_by_revenue(10, date_from, date_to)
        top_clients = [
            TopClientDTO(
                name=c["name"],
                count=int(c["count"]),
                revenue=Decimal(str(c["revenue"])),
                profit=Decimal(str(c["profit"])),
            ) for c in top_clients_raw
        ]

        return ReportsContextDTO(
            summary=summary,
            top_products=top_products,
            top_clients=top_clients,
            client_debts=client_debts,
            debt_totals=debt_totals,
            expenses_by_cat_labels=expenses_by_cat_labels,
            expenses_by_cat_totals=expenses_by_cat_totals,
            expenses_total=expenses_total,
            net_profit=net_profit,
            cogs=cogs,
            gross_margin=gross_margin,
            gross_margin_pct=gross_margin_pct,
            net_margin_pct=net_margin_pct,
            chart_labels=chart_labels,
            chart_sales=chart_sales,
            chart_purchases=chart_purchases,
            chart_expenses=chart_expenses,
            chart_profit=chart_profit,
            daily_labels=daily_labels,
            daily_totals=daily_totals,
            daily_profits=daily_profits,
            date_from=date_from,
            date_to=date_to,
        )
