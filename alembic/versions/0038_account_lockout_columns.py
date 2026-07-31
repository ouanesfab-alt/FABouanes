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
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
