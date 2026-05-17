"""Add performance indexes for dashboard queries."""
from __future__ import annotations

from alembic import op


revision = "0002_perf_indexes"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_materials_stock_alert ON raw_materials(stock_qty, alert_threshold)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_sale_date_id ON sales(sale_date, id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_sale_date_id ON raw_sales(sale_date, id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_type_date_amount ON payments(payment_type, payment_date, amount)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_payments_type_date_amount")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_sale_date_id")
    op.execute("DROP INDEX IF EXISTS idx_sales_sale_date_id")
    op.execute("DROP INDEX IF EXISTS idx_raw_materials_stock_alert")
