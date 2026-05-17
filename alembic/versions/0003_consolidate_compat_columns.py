"""Consolidate compatibility columns into Alembic."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = '0003_consolidate_compat_columns'
down_revision = '42e8e51bd5b4'

branch_labels = None
depends_on = None

def _column_exists(table_name, column_name):
    bind = op.get_bind()
    insp = sa_inspect(bind)
    columns = [c['name'] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # List of (table, column, type, server_default)
    columns_to_add = [
        ('clients', 'opening_credit', sa.Float(), '0'),
        ('users', 'must_change_password', sa.Integer(), '0'),
        ('users', 'is_active', sa.Integer(), '1'),
        ('users', 'last_login_at', sa.Text(), None),
        ('users', 'last_password_change_at', sa.Text(), None),
        ('raw_materials', 'sale_price', sa.Float(), '0'),
        ('raw_materials', 'alert_threshold', sa.Float(), '0'),
        ('raw_materials', 'threshold_qty', sa.Float(), '0'),
        ('finished_products', 'avg_cost', sa.Float(), '0'),
        ('sales', 'document_id', sa.Integer(), None),
        ('sales', 'cost_price_snapshot', sa.Float(), '0'),
        ('sales', 'profit_amount', sa.Float(), '0'),
        ('raw_sales', 'document_id', sa.Integer(), None),
        ('raw_sales', 'custom_item_name', sa.Text(), None),
        ('raw_sales', 'cost_price_snapshot', sa.Float(), '0'),
        ('raw_sales', 'profit_amount', sa.Float(), '0'),
        ('purchases', 'unit', sa.Text(), 'kg'),
        ('purchases', 'document_id', sa.Integer(), None),
        ('purchases', 'custom_item_name', sa.Text(), None),
        ('payments', 'raw_sale_id', sa.Integer(), None),
        ('payments', 'sale_kind', sa.Text(), None),
        ('payments', 'payment_type', sa.Text(), 'versement'),
        ('payments', 'allocation_meta', sa.Text(), None),
        ('activity_logs', 'user_id', sa.Integer(), None),
        ('activity_logs', 'entity_type', sa.Text(), None),
        ('activity_logs', 'entity_id', sa.Integer(), None),
        ('activity_logs', 'details', sa.Text(), None),
        ('activity_logs', 'old_value', sa.Text(), None),
        ('activity_logs', 'new_value', sa.Text(), None),
        ('activity_logs', 'ip_address', sa.Text(), None),
    ]

    for table, col, type_, default in columns_to_add:
        if not _column_exists(table, col):
            op.add_column(table, sa.Column(col, type_, server_default=default, nullable=False if default is not None else True))

def downgrade() -> None:
    # Reversing this is tricky because we might delete columns that were there before
    # but for completeness, we could drop them if they exist.
    # However, since this is a consolidation, we might want to keep it simple.
    pass
