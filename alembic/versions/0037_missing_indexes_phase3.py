"""missing indexes phase3

Revision ID: 0037_missing_indexes_phase3
Revises: 0036_sabrina_memory
Create Date: 2026-07-13 19:45:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0037_missing_indexes_phase3'
down_revision = '0036_sabrina_memory'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_credit_client ON sales(client_id, total) WHERE sale_type = 'credit'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_credit_client ON raw_sales(client_id, total) WHERE sale_type = 'credit'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_client_date_type ON sales(client_id, sale_date, sale_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date ON purchases(supplier_id, purchase_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_finished_product_id ON purchases(finished_product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prod_items_material_id ON production_batch_items(raw_material_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_saved_recipe_items_material_id ON saved_recipe_items(raw_material_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_performance_logs_created_at ON performance_logs(created_at)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sales_credit_client")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_credit_client")
    op.execute("DROP INDEX IF EXISTS idx_sales_client_date_type")
    op.execute("DROP INDEX IF EXISTS idx_purchases_supplier_date")
    op.execute("DROP INDEX IF EXISTS idx_finished_products_name")
    op.execute("DROP INDEX IF EXISTS idx_raw_materials_name")
    op.execute("DROP INDEX IF EXISTS idx_purchases_finished_product_id")
    op.execute("DROP INDEX IF EXISTS idx_prod_items_material_id")
    op.execute("DROP INDEX IF EXISTS idx_saved_recipe_items_material_id")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_actor_user_id")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_entity")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_status")
    op.execute("DROP INDEX IF EXISTS idx_activity_logs_entity")
    op.execute("DROP INDEX IF EXISTS idx_performance_logs_created_at")
