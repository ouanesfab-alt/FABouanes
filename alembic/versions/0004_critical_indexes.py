"""Add critical indexes for performance and reliability."""
from __future__ import annotations

from alembic import op


revision = "0004_critical_indexes"
down_revision = "0003_consolidate_compat_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use CREATE INDEX IF NOT EXISTS (PG supports it)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_sale_date ON sales(sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_client_date ON sales(client_id, sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_raw_sales_sale_date ON raw_sales(sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_raw_sales_client_date ON raw_sales(client_id, sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_purchase_date ON purchases(purchase_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_date ON purchases(supplier_id, purchase_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_sale_id ON payments(sale_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_raw_sale_id ON payments(raw_sale_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activity_logs_entity ON activity_logs(entity_type, entity_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_activity_logs_entity")
    op.execute("DROP INDEX IF EXISTS ix_payments_raw_sale_id")
    op.execute("DROP INDEX IF EXISTS ix_payments_sale_id")
    op.execute("DROP INDEX IF EXISTS ix_purchases_supplier_date")
    op.execute("DROP INDEX IF EXISTS ix_purchases_purchase_date")
    op.execute("DROP INDEX IF EXISTS ix_raw_sales_client_date")
    op.execute("DROP INDEX IF EXISTS ix_raw_sales_sale_date")
    op.execute("DROP INDEX IF EXISTS ix_sales_client_date")
    op.execute("DROP INDEX IF EXISTS ix_sales_sale_date")
