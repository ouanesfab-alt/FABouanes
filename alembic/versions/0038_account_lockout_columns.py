"""Add user account lockout columns

Revision ID: 0038_account_lockout_columns
Revises: 0037_missing_indexes_phase3
Create Date: 2026-07-31 04:15:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0038_account_lockout_columns'
down_revision = '0037_missing_indexes_phase3'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count INTEGER DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ")

def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS locked_until")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS failed_login_count")

