"""Fix financial data types

Revision ID: 0005_fix_financial_types
Revises: 0004_critical_indexes
Create Date: 2026-05-17 20:15:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0005_fix_financial_types'
down_revision = '0004_critical_indexes'
branch_labels = None
depends_on = None

columns_to_fix = [
    # (table, column, default_val)
    ('purchases', 'quantity', '0'),
    ('purchases', 'unit_price', '0'),
    ('purchases', 'total', '0'),
    
    ('sales', 'quantity', '0'),
    ('sales', 'unit_price', '0'),
    ('sales', 'total', '0'),
    ('sales', 'amount_paid', '0'),
    ('sales', 'balance_due', '0'),
    ('sales', 'cost_price_snapshot', '0'),
    ('sales', 'profit_amount', '0'),
    
    ('raw_sales', 'quantity', '0'),
    ('raw_sales', 'unit_price', '0'),
    ('raw_sales', 'total', '0'),
    ('raw_sales', 'amount_paid', '0'),
    ('raw_sales', 'balance_due', '0'),
    ('raw_sales', 'cost_price_snapshot', '0'),
    ('raw_sales', 'profit_amount', '0'),
    
    ('payments', 'amount', '0'),
    
    ('sale_documents', 'total', '0'),
    ('sale_documents', 'amount_paid', '0'),
    ('sale_documents', 'balance_due', '0'),
    
    ('purchase_documents', 'total', '0'),
    
    ('raw_materials', 'stock_qty', '0'),
    ('raw_materials', 'avg_cost', '0'),
    ('raw_materials', 'sale_price', '0'),
    ('raw_materials', 'alert_threshold', '0'),
    ('raw_materials', 'threshold_qty', '0'),
    
    ('finished_products', 'sale_price', '0'),
    ('finished_products', 'avg_cost', '0'),
    ('finished_products', 'stock_qty', '0'),
]

def upgrade() -> None:
    # We alter all of these columns to NUMERIC(14,2) using PostgreSQL ALTER TABLE ALTER COLUMN TYPE using USING clause
    # This is much cleaner and more direct than creating a parallel column, copying, dropping and renaming.
    # In PostgreSQL:
    # ALTER TABLE purchases ALTER COLUMN quantity TYPE NUMERIC(14,2) USING ROUND(quantity::numeric, 2);
    for table, col, default in columns_to_fix:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE NUMERIC(14,2) USING ROUND("{col}"::numeric, 2)')

def downgrade() -> None:
    # Convert back to DOUBLE PRECISION
    for table, col, default in columns_to_fix:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE DOUBLE PRECISION USING "{col}"::float8')
