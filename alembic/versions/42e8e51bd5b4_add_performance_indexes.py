"""Add performance indexes

Revision ID: 42e8e51bd5b4
Revises: 0002_perf_indexes
Create Date: 2026-05-09 19:23:38.422673
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42e8e51bd5b4'
down_revision = '0002_perf_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index pour accélérer les rapports, le dashboard et l'espace bons
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_client ON sales(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_date ON raw_sales(sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_client ON raw_sales(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_client ON payments(client_id)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_date")
    op.execute("DROP INDEX IF EXISTS idx_sales_client")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_client")
    op.execute("DROP INDEX IF EXISTS idx_purchases_date")
    op.execute("DROP INDEX IF EXISTS idx_purchases_supplier")
    op.execute("DROP INDEX IF EXISTS idx_payments_date")
    op.execute("DROP INDEX IF EXISTS idx_payments_client")
