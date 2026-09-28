"""perf indexes v2_3

Revision ID: 0039_perf_indexes_v2_3
Revises: 0038_account_lockout_columns
Create Date: 2026-09-16 15:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0039_perf_indexes_v2_3"
down_revision = "0038_account_lockout_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_production_batches_date ON production_batches(production_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_production_batches_product_id ON production_batches(finished_product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales(finished_product_id, sale_date)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_production_batches_date")
    op.execute("DROP INDEX IF EXISTS idx_production_batches_product_id")
    op.execute("DROP INDEX IF EXISTS idx_expenses_date")
    op.execute("DROP INDEX IF EXISTS idx_expenses_category")
    op.execute("DROP INDEX IF EXISTS idx_payments_date")
    op.execute("DROP INDEX IF EXISTS idx_sales_product_date")
