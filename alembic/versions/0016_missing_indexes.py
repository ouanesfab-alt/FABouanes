"""Add missing performance indexes

Revision ID: 0016_missing_indexes
Revises: 0015_client_stats_view
Create Date: 2026-05-20 00:16:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = '0016_missing_indexes'
down_revision = '0015_client_stats_view'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_kind, item_id, created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_stock_movements_reference ON stock_movements(reference_type, reference_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_performance_logs_kind ON performance_logs(kind, created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_imported_client_history_client ON imported_client_history(client_id, created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_purchases_finished_product_id ON purchases(finished_product_id) WHERE finished_product_id IS NOT NULL')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_audit_logs_entity')
    op.execute('DROP INDEX IF EXISTS idx_purchases_finished_product_id')
    op.execute('DROP INDEX IF EXISTS idx_imported_client_history_client')
    op.execute('DROP INDEX IF EXISTS idx_performance_logs_kind')
    op.execute('DROP INDEX IF EXISTS idx_stock_movements_reference')
    op.execute('DROP INDEX IF EXISTS idx_stock_movements_item')
