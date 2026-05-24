"""Add composite indexes for client-centric timeline queries

Revision ID: 0023_client_timeline_idx
Revises: 0022_perf_idx
Create Date: 2026-05-23 22:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = '0023_client_timeline_idx'
down_revision = '0022_perf_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Speed up the UNION ALL timeline query used by client detail pages
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_client_date ON sales(client_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_client_date ON raw_sales(client_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_client_date ON payments(client_id, payment_date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_client_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_client_date")
    op.execute("DROP INDEX IF EXISTS idx_payments_client_date")
