"""Add document foreign keys

Revision ID: 0006_add_document_fk
Revises: 0005_fix_financial_types
Create Date: 2026-05-17 20:20:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0006_add_document_fk'
down_revision = '0005_fix_financial_types'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Clean up any orphaned document_id references to prevent FK violation failures
    op.execute("UPDATE sales SET document_id = NULL WHERE document_id IS NOT NULL AND document_id NOT IN (SELECT id FROM sale_documents)")
    op.execute("UPDATE purchases SET document_id = NULL WHERE document_id IS NOT NULL AND document_id NOT IN (SELECT id FROM purchase_documents)")

    # 2. Add foreign key constraints (dropping first if they already exist to be safe and idempotent)
    op.execute("ALTER TABLE sales DROP CONSTRAINT IF EXISTS fk_sales_document")
    op.execute("""
        ALTER TABLE sales 
        ADD CONSTRAINT fk_sales_document 
        FOREIGN KEY (document_id) 
        REFERENCES sale_documents(id) 
        ON DELETE RESTRICT
    """)
    op.execute("ALTER TABLE purchases DROP CONSTRAINT IF EXISTS fk_purchases_document")
    op.execute("""
        ALTER TABLE purchases 
        ADD CONSTRAINT fk_purchases_document 
        FOREIGN KEY (document_id) 
        REFERENCES purchase_documents(id) 
        ON DELETE RESTRICT
    """)

def downgrade() -> None:
    # Remove foreign key constraints
    op.execute("ALTER TABLE sales DROP CONSTRAINT IF EXISTS fk_sales_document")
    op.execute("ALTER TABLE purchases DROP CONSTRAINT IF EXISTS fk_purchases_document")
