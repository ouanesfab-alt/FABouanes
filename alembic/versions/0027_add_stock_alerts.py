"""Add stock_alerts table

Revision ID: 0027_add_stock_alerts
Revises: 0026_fix_financial_decimal_types
Create Date: 2026-05-24 17:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0027_add_stock_alerts'
down_revision = '0026_fix_financial_decimal_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (bootstrapped)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'stock_alerts' not in tables:
        op.create_table(
            'stock_alerts',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('product_type', sa.Text(), nullable=False),
            sa.Column('product_id', sa.BigInteger(), nullable=False),
            sa.Column('product_name', sa.Text(), nullable=False),
            sa.Column('current_qty', sa.Numeric(precision=15, scale=4), nullable=False),
            sa.Column('threshold_qty', sa.Numeric(precision=15, scale=4), nullable=False),
            sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('idx_stock_alerts_product', 'stock_alerts', ['product_type', 'product_id'])
        op.create_index('idx_stock_alerts_triggered_at', 'stock_alerts', ['triggered_at'])
        
    # Also ensure finished_products has alert_threshold column
    columns = [c['name'] for c in inspector.get_columns('finished_products')]
    if 'alert_threshold' not in columns:
        op.add_column('finished_products', sa.Column('alert_threshold', sa.Numeric(precision=15, scale=4), server_default='0.0000', nullable=False))


def downgrade() -> None:
    op.drop_table('stock_alerts')
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('finished_products')]
    if 'alert_threshold' in columns:
        op.drop_column('finished_products', 'alert_threshold')
