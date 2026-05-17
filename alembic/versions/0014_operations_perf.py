"""Add indexes for operations sorting and VACUUM schedule

Revision ID: 0014_operations_perf
Revises: 0013_add_bi_reporting_indexes
Create Date: 2026-05-18 01:16:00.000000
"""
from __future__ import annotations

from alembic import op

revision = '0014_operations_perf'
down_revision = '0013_add_bi_reporting_indexes'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Index for operations sorting: ORDER BY sale_date DESC, created_at DESC
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_date_created ON sales (sale_date DESC, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_date_created ON raw_sales (sale_date DESC, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_date_created ON purchases (purchase_date DESC, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_date_created ON payments (payment_date DESC, created_at DESC)")

    # 2. Index on expenses.date for reports monthly aggregation
    op.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses (date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_expenses_date")
    op.execute("DROP INDEX IF EXISTS idx_payments_date_created")
    op.execute("DROP INDEX IF EXISTS idx_purchases_date_created")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_date_created")
    op.execute("DROP INDEX IF EXISTS idx_sales_date_created")
