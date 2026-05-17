"""Add BI reporting composite indexes

Revision ID: 0013_add_bi_reporting_indexes
Revises: 0012_add_fts_postgresql
Create Date: 2026-05-17 21:05:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0013_add_bi_reporting_indexes'
down_revision = '0012_add_fts_postgresql'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Composite index for sales BI/FIFO reporting
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_reporting ON sales (sale_type, sale_date, client_id)")
    
    # 2. Composite index for raw sales BI/FIFO reporting
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_reporting ON raw_sales (sale_type, sale_date, client_id)")
    
    # 3. Composite index for payment chronology
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_chronology ON payments (client_id, payment_date, id)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_reporting")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_reporting")
    op.execute("DROP INDEX IF EXISTS idx_payments_chronology")
