"""database optimization - type conversions

Revision ID: 0030_type_conversions
Revises: 0029_db_opt_idx_views
Create Date: 2026-05-25 16:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0030_type_conversions'
down_revision = '0029_db_opt_idx_views'
branch_labels = None
depends_on = None

columns_to_fix = [
    ('clients', 'opening_credit'),
    ('imported_client_history', 'debit_amount'),
    ('imported_client_history', 'credit_amount'),
    ('imported_client_history', 'running_balance'),
    ('raw_materials', 'stock_qty'),
    ('raw_materials', 'avg_cost'),
    ('raw_materials', 'sale_price'),
    ('raw_materials', 'alert_threshold'),
    ('raw_materials', 'threshold_qty'),
    ('finished_products', 'stock_qty'),
    ('finished_products', 'sale_price'),
    ('finished_products', 'avg_cost'),
    ('stock_movements', 'quantity'),
    ('stock_movements', 'stock_before'),
    ('stock_movements', 'stock_after'),
    ('purchase_documents', 'total'),
    ('sale_documents', 'total'),
    ('sale_documents', 'amount_paid'),
    ('sale_documents', 'balance_due'),
    ('purchases', 'quantity'),
    ('purchases', 'unit_price'),
    ('purchases', 'total'),
    ('sales', 'quantity'),
    ('sales', 'unit_price'),
    ('sales', 'total'),
    ('sales', 'amount_paid'),
    ('sales', 'balance_due'),
    ('sales', 'cost_price_snapshot'),
    ('sales', 'profit_amount'),
    ('raw_sales', 'quantity'),
    ('raw_sales', 'unit_price'),
    ('raw_sales', 'total'),
    ('raw_sales', 'amount_paid'),
    ('raw_sales', 'balance_due'),
    ('raw_sales', 'cost_price_snapshot'),
    ('raw_sales', 'profit_amount'),
    ('payments', 'amount'),
    ('production_batches', 'output_quantity'),
    ('production_batches', 'production_cost'),
    ('production_batches', 'unit_cost'),
    ('production_batch_items', 'quantity'),
    ('production_batch_items', 'unit_cost_snapshot'),
    ('production_batch_items', 'line_cost'),
    ('saved_recipe_items', 'quantity'),
]

def upgrade() -> None:
    # 1. Convert production_batches.production_date to DATE
    op.execute("ALTER TABLE production_batches ALTER COLUMN production_date TYPE DATE USING production_date::DATE")

    # 2. Convert users must_change_password and is_active from INTEGER to BOOLEAN
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password TYPE BOOLEAN USING (must_change_password::int != 0)")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password SET DEFAULT FALSE")
    
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE BOOLEAN USING (is_active::int != 0)")
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE")

    # 3. Alter all financial and quantity columns to NUMERIC(15, 4)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, col in columns_to_fix:
        cols_in_table = [c['name'] for c in inspector.get_columns(table)]
        if col in cols_in_table:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE NUMERIC(15,4) USING "{col}"::numeric')


def downgrade() -> None:
    # 1. Revert production_batches.production_date to TEXT
    op.execute("ALTER TABLE production_batches ALTER COLUMN production_date TYPE TEXT USING production_date::TEXT")

    # 2. Revert users must_change_password and is_active to INTEGER
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password TYPE INTEGER USING (CASE WHEN must_change_password THEN 1 ELSE 0 END)")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password SET DEFAULT 0")

    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE INTEGER USING (CASE WHEN is_active THEN 1 ELSE 0 END)")
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT 1")

    # 3. Revert financial and quantity columns to DOUBLE PRECISION
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, col in columns_to_fix:
        cols_in_table = [c['name'] for c in inspector.get_columns(table)]
        if col in cols_in_table:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE DOUBLE PRECISION USING "{col}"::double precision')
