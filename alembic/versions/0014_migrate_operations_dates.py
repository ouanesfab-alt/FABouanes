"""Migrate core operations text date columns to native DATE type

Revision ID: 0014_migrate_operations_dates
Revises: 0013_migrate_expenses_types
Create Date: 2026-05-18 17:20:00.000000
"""
from __future__ import annotations

from alembic import op


revision = '0014_migrate_operations_dates'
down_revision = '0013_migrate_expenses_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Convert columns using safe PostgreSQL DATE castings
    op.execute("ALTER TABLE purchase_documents ALTER COLUMN purchase_date TYPE DATE USING (purchase_date::date)")
    op.execute("ALTER TABLE sale_documents ALTER COLUMN sale_date TYPE DATE USING (sale_date::date)")
    op.execute("ALTER TABLE purchases ALTER COLUMN purchase_date TYPE DATE USING (purchase_date::date)")
    op.execute("ALTER TABLE sales ALTER COLUMN sale_date TYPE DATE USING (sale_date::date)")
    op.execute("ALTER TABLE raw_sales ALTER COLUMN sale_date TYPE DATE USING (sale_date::date)")
    op.execute("ALTER TABLE payments ALTER COLUMN payment_date TYPE DATE USING (payment_date::date)")


def downgrade() -> None:
    # Convert back to TEXT if necessary
    op.execute("ALTER TABLE purchase_documents ALTER COLUMN purchase_date TYPE TEXT USING (purchase_date::text)")
    op.execute("ALTER TABLE sale_documents ALTER COLUMN sale_date TYPE TEXT USING (sale_date::text)")
    op.execute("ALTER TABLE purchases ALTER COLUMN purchase_date TYPE TEXT USING (purchase_date::text)")
    op.execute("ALTER TABLE sales ALTER COLUMN sale_date TYPE TEXT USING (sale_date::text)")
    op.execute("ALTER TABLE raw_sales ALTER COLUMN sale_date TYPE TEXT USING (sale_date::text)")
    op.execute("ALTER TABLE payments ALTER COLUMN payment_date TYPE TEXT USING (payment_date::text)")
