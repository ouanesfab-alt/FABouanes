"""database optimization indexes and views - missing columns

Revision ID: 0029_db_opt_idx_views
Revises: None
Create Date: 2026-05-25 15:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0029_db_opt_idx_views'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. raw_sales: custom_item_name TEXT
    columns_raw_sales = [c['name'] for c in inspector.get_columns('raw_sales')]
    if 'custom_item_name' not in columns_raw_sales:
        op.add_column('raw_sales', sa.Column('custom_item_name', sa.Text(), nullable=True))

    # 2. purchases: custom_item_name TEXT
    columns_purchases = [c['name'] for c in inspector.get_columns('purchases')]
    if 'custom_item_name' not in columns_purchases:
        op.add_column('purchases', sa.Column('custom_item_name', sa.Text(), nullable=True))

    # 3. activity_logs: user_id INTEGER, old_value TEXT, new_value TEXT, ip_address TEXT
    columns_activity_logs = [c['name'] for c in inspector.get_columns('activity_logs')]
    if 'user_id' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('user_id', sa.Integer(), nullable=True))
    if 'old_value' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('old_value', sa.Text(), nullable=True))
    if 'new_value' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('new_value', sa.Text(), nullable=True))
    if 'ip_address' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('ip_address', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('raw_sales', 'custom_item_name')
    op.drop_column('purchases', 'custom_item_name')
    op.drop_column('activity_logs', 'user_id')
    op.drop_column('activity_logs', 'old_value')
    op.drop_column('activity_logs', 'new_value')
    op.drop_column('activity_logs', 'ip_address')
