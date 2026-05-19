"""Add offline operation receipts and targeted performance indexes

Revision ID: 0016_offline_receipts
Revises: 0015_client_stats_view
Create Date: 2026-05-19 19:00:00.000000
"""
from __future__ import annotations

from alembic import op


revision = "0016_offline_receipts"
down_revision = "0015_client_stats_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offline_operation_receipts (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            client_operation_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'processing',
            request_json TEXT,
            response_json TEXT,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ,
            UNIQUE(user_id, client_operation_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_offline_receipts_user_created ON offline_operation_receipts(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_offline_receipts_status ON offline_operation_receipts(status, updated_at)")

    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_open_balance_client ON sales(client_id, sale_date, id) WHERE balance_due > 0")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_open_balance_client ON raw_sales(client_id, sale_date, id) WHERE balance_due > 0")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_created_at ON raw_sales(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_created_at ON purchases(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_purchases_created_at")
    op.execute("DROP INDEX IF EXISTS idx_payments_created_at")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_created_at")
    op.execute("DROP INDEX IF EXISTS idx_sales_created_at")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_open_balance_client")
    op.execute("DROP INDEX IF EXISTS idx_sales_open_balance_client")
    op.execute("DROP TABLE IF EXISTS offline_operation_receipts")
