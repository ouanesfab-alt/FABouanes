"""Add composite search indexes for transaction histories

Revision ID: 0022_perf_idx
Revises: 0021_fix_comptoir_triggers
Create Date: 2026-05-23 21:50:00.000000
"""
from __future__ import annotations

from alembic import op

revision = '0022_perf_idx'
down_revision = '0021_fix_comptoir_triggers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add high-performance composite indexes to speed up historical lookups
    op.execute("CREATE INDEX IF NOT EXISTS idx_client_history_search ON client_history(client_id, operation_date DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_reporting_composite ON sales(finished_product_id, sale_date DESC, client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_reporting_composite ON raw_sales(raw_material_id, sale_date DESC, client_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_client_history_search")
    op.execute("DROP INDEX IF EXISTS idx_sales_reporting_composite")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_reporting_composite")
