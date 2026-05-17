from __future__ import annotations

from typing import Any
from decimal import Decimal
from pydantic import BaseModel

class ReportsSummaryDTO(BaseModel):
    total_sales: Decimal
    total_profit: Decimal
    total_purchases: Decimal
    total_payments: Decimal

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
    30_to_90: Decimal
    over_90: Decimal
    avg_delay: int | None
    limit: Decimal
    limit_utilized_pct: float
    limit_utilized_pct_clamped: float
    limit_exceeded: bool

class DebtTotalsDTO(BaseModel):
    under_30: Decimal
    30_to_90: Decimal
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
    monthly_labels: list[str]
    monthly_sales: list[float]
    monthly_purchases: list[float]
    date_from: str | None
    date_to: str | None
