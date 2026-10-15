"""0003_add_credit_limit_and_production_yield - Add credit limit to clients and yield/loss to production batches.

Revision ID: 0003_credit_limit_and_yield
Revises: 0002_triggers_and_views
Create Date: 2026-10-15 18:45:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_credit_limit_and_yield"
down_revision = "0002_triggers_and_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add credit_limit to clients if not already present
    client_cols = [c["name"] for c in inspector.get_columns("clients")]
    if "credit_limit" not in client_cols:
        with op.batch_alter_table("clients") as batch_op:
            batch_op.add_column(sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True))

    # 2. Add yield and waste fields to production_batches if not already present
    prod_cols = [c["name"] for c in inspector.get_columns("production_batches")]
    with op.batch_alter_table("production_batches") as batch_op:
        if "total_raw_quantity" not in prod_cols:
            batch_op.add_column(sa.Column("total_raw_quantity", sa.Numeric(15, 2), nullable=True, server_default="0.00"))
        if "waste_quantity" not in prod_cols:
            batch_op.add_column(sa.Column("waste_quantity", sa.Numeric(15, 2), nullable=True, server_default="0.00"))
        if "yield_rate" not in prod_cols:
            batch_op.add_column(sa.Column("yield_rate", sa.Numeric(6, 2), nullable=True, server_default="100.00"))


def downgrade() -> None:
    with op.batch_alter_table("production_batches") as batch_op:
        batch_op.drop_column("yield_rate")
        batch_op.drop_column("waste_quantity")
        batch_op.drop_column("total_raw_quantity")

    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_column("credit_limit")
