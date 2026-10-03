"""add high performance indexes on documents and search vectors

Revision ID: 0042_documents_indexes_perf
Revises: 0041_consolidate_bootstrap
Create Date: 2026-10-03 14:30:00.000000
"""
from __future__ import annotations

from alembic import op


revision = "0042_documents_indexes_perf"
down_revision = "0041_consolidate_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Performance indexes for documents
    op.execute("CREATE INDEX IF NOT EXISTS idx_sale_documents_client_date ON sale_documents(client_id, sale_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sale_documents_date ON sale_documents(sale_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sale_documents_doc_number ON sale_documents(doc_number);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchase_documents_supplier_date ON purchase_documents(supplier_id, purchase_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchase_documents_date ON purchase_documents(purchase_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchase_documents_doc_number ON purchase_documents(doc_number);")

    # 2. Case-insensitive search indexes for lookup acceleration
    op.execute("CREATE INDEX IF NOT EXISTS idx_clients_name_lower ON clients(LOWER(name));")
    op.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name_lower ON suppliers(LOWER(name));")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users(LOWER(username));")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sale_documents_client_date;")
    op.execute("DROP INDEX IF EXISTS idx_sale_documents_date;")
    op.execute("DROP INDEX IF EXISTS idx_sale_documents_doc_number;")
    op.execute("DROP INDEX IF EXISTS idx_purchase_documents_supplier_date;")
    op.execute("DROP INDEX IF EXISTS idx_purchase_documents_date;")
    op.execute("DROP INDEX IF EXISTS idx_purchase_documents_doc_number;")
    op.execute("DROP INDEX IF EXISTS idx_clients_name_lower;")
    op.execute("DROP INDEX IF EXISTS idx_suppliers_name_lower;")
    op.execute("DROP INDEX IF EXISTS idx_users_username_lower;")
