"""Fix column types for production_date and user flags

Revision ID: 0017_fix_column_types
Revises: 0016_missing_indexes
Create Date: 2026-05-20 00:16:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = '0017_fix_column_types'
down_revision = '0016_missing_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix production_date from TEXT to proper DATE type
    op.execute("ALTER TABLE production_batches ALTER COLUMN production_date TYPE DATE USING production_date::DATE")

    # Fix user boolean flags from INTEGER to proper BOOLEAN type
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password TYPE BOOLEAN USING (must_change_password::int != 0)")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE BOOLEAN USING (is_active::int != 0)")


def downgrade() -> None:
    # Revert production_date back to TEXT
    op.execute("ALTER TABLE production_batches ALTER COLUMN production_date TYPE TEXT USING production_date::TEXT")

    # Revert user boolean flags back to INTEGER
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password TYPE INTEGER USING must_change_password::int")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE INTEGER USING is_active::int")
