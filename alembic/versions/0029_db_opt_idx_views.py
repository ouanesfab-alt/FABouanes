"""database optimization indexes and views

Revision ID: 0029_db_opt_idx_views
Revises: 0028_add_manager_role
Create Date: 2026-05-25 15:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision = '0029_db_opt_idx_views'
down_revision = '0028_add_manager_role'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create covering composite indexes for dashboard and reporting queries
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_covering_daily ON sales(sale_date, total, profit_amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_covering_daily ON raw_sales(sale_date, total, profit_amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_covering_daily ON payments(payment_date, amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_covering_daily ON purchases(purchase_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_material_date ON raw_sales(raw_material_id, sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_covering_type_date ON sales(sale_type, sale_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_covering_type_date ON raw_sales(sale_type, sale_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_covering_type_date ON payments(payment_type, payment_date, amount)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_payments_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_purchases_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_material_date")
    op.execute("DROP INDEX IF EXISTS idx_sales_covering_type_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_covering_type_date")
    op.execute("DROP INDEX IF EXISTS idx_payments_covering_type_date")
