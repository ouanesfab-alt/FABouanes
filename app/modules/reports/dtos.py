from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class ReportsSummaryDTO(BaseModel):
    total_sales: Decimal
    total_profit: Decimal
    total_purchases: Decimal
    total_payments: Decimal
    nb_sales: int
    nb_purchases: int
    nb_payments: int

class TopProductDTO(BaseModel):
    name: str
    qty: float
    revenue: Decimal
    profit: Decimal

class TopClientDTO(BaseModel):
    name: str
    count: int
    revenue: Decimal
    profit: Decimal

class ClientDebtDTO(BaseModel):
    id: int
    name: str
    debt: Decimal
    under_30: Decimal
    days_30_to_90: Decimal
    over_90: Decimal
    avg_delay: int | None
    limit: Decimal
    limit_utilized_pct: float
    limit_utilized_pct_clamped: float
    limit_exceeded: bool

class DebtTotalsDTO(BaseModel):
    under_30: Decimal
    days_30_to_90: Decimal
    over_90: Decimal
    outstanding: Decimal

class ReportsContextDTO(BaseModel):
    summary: ReportsSummaryDTO
    top_products: list[TopProductDTO]
    top_clients: list[TopClientDTO]
    client_debts: list[ClientDebtDTO]
    debt_totals: DebtTotalsDTO
    expenses_by_cat_labels: list[str]
    expenses_by_cat_totals: list[float]
    expenses_total: Decimal
    net_profit: Decimal
    cogs: Decimal
    gross_margin: Decimal
    gross_margin_pct: float
    net_margin_pct: float
    chart_labels: list[str]
    chart_sales: list[float]
    chart_purchases: list[float]
    chart_expenses: list[float]
    chart_profit: list[float]
    daily_labels: list[str]
    daily_totals: list[float]
    daily_profits: list[float]
    date_from: str | None
    date_to: str | None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
