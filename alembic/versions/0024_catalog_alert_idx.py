"""Add composite indexes for catalog alert queries

Revision ID: 0024_catalog_alert_idx
Revises: 0023_client_timeline_idx
Create Date: 2026-05-24 12:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision = '0024_catalog_alert_idx'
down_revision = '0023_client_timeline_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Speed up threshold alerts checks
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_materials_alert ON raw_materials(stock_qty, alert_threshold)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finished_products_alert ON finished_products(stock_qty)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_raw_materials_alert")
    op.execute("DROP INDEX IF EXISTS idx_finished_products_alert")
