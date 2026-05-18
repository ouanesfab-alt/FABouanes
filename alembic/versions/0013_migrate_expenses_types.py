"""Migrate expenses date and timestamp columns to native DATE and TIMESTAMPTZ types

Revision ID: 0013_migrate_expenses_types
Revises: 0012_operations_perf
Create Date: 2026-05-18 16:55:00.000000
"""
from __future__ import annotations

from alembic import op

revision = '0013_migrate_expenses_types'
down_revision = '0012_operations_perf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Convert columns using safe PostgreSQL castings
    op.execute("ALTER TABLE expenses ALTER COLUMN date TYPE DATE USING (date::date)")
    op.execute("ALTER TABLE expenses ALTER COLUMN created_at TYPE TIMESTAMPTZ USING (created_at::timestamptz)")
    op.execute("ALTER TABLE expenses ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING (updated_at::timestamptz)")
    
    # 2. Add defaults to timestamptz columns
    op.execute("ALTER TABLE expenses ALTER COLUMN created_at SET DEFAULT NOW()")
    op.execute("ALTER TABLE expenses ALTER COLUMN updated_at SET DEFAULT NOW()")


def downgrade() -> None:
    # Convert back to TEXT if necessary
    op.execute("ALTER TABLE expenses ALTER COLUMN date TYPE TEXT USING (date::text)")
    op.execute("ALTER TABLE expenses ALTER COLUMN created_at TYPE TEXT USING (created_at::text)")
    op.execute("ALTER TABLE expenses ALTER COLUMN updated_at TYPE TEXT USING (updated_at::text)")
