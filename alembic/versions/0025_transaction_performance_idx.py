"""Add composite indexes for transactional performance optimization

Revision ID: 0025_transaction_performance_idx
Revises: 0024_catalog_alert_idx
Create Date: 2026-05-24 14:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision = '0025_transaction_performance_idx'
down_revision = '0024_catalog_alert_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(finished_product_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_material ON purchases(raw_material_id, purchase_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_client_date ON payments(client_id, payment_date DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_product")
    op.execute("DROP INDEX IF EXISTS idx_purchases_material")
    op.execute("DROP INDEX IF EXISTS idx_payments_client_date")
