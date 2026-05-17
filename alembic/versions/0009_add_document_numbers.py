"""Add document numbers

Revision ID: 0009_add_document_numbers
Revises: 0008_add_updated_at
Create Date: 2026-05-17 20:35:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0009_add_document_numbers'
down_revision = '0008_add_updated_at'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    
    # Check if doc_number already exists in sale_documents
    has_sales_doc_number = bind.execute(sa.text("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sale_documents' AND column_name = 'doc_number'
    """)).fetchone()
    
    if not has_sales_doc_number:
        # Add doc_number column to sale_documents (initially nullable)
        op.execute('ALTER TABLE sale_documents ADD COLUMN doc_number TEXT')
        # Populate existing rows uniquely
        op.execute("UPDATE sale_documents SET doc_number = 'BV-2026-' || LPAD(id::text, 5, '0') WHERE doc_number IS NULL")
        # Make non-nullable and add UNIQUE constraint
        op.execute('ALTER TABLE sale_documents ALTER COLUMN doc_number SET NOT NULL')
        op.execute('ALTER TABLE sale_documents ADD CONSTRAINT uq_sale_documents_doc_number UNIQUE (doc_number)')

    # Check if doc_number already exists in purchase_documents
    has_purchases_doc_number = bind.execute(sa.text("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'purchase_documents' AND column_name = 'doc_number'
    """)).fetchone()
    
    if not has_purchases_doc_number:
        # Add doc_number column to purchase_documents (initially nullable)
        op.execute('ALTER TABLE purchase_documents ADD COLUMN doc_number TEXT')
        # Populate existing rows uniquely
        op.execute("UPDATE purchase_documents SET doc_number = 'BA-2026-' || LPAD(id::text, 5, '0') WHERE doc_number IS NULL")
        # Make non-nullable and add UNIQUE constraint
        op.execute('ALTER TABLE purchase_documents ALTER COLUMN doc_number SET NOT NULL')
        op.execute('ALTER TABLE purchase_documents ADD CONSTRAINT uq_purchase_documents_doc_number UNIQUE (doc_number)')

def downgrade() -> None:
    op.execute('ALTER TABLE sale_documents DROP CONSTRAINT IF EXISTS uq_sale_documents_doc_number')
    op.execute('ALTER TABLE sale_documents DROP COLUMN IF EXISTS doc_number')
    
    op.execute('ALTER TABLE purchase_documents DROP CONSTRAINT IF EXISTS uq_purchase_documents_doc_number')
    op.execute('ALTER TABLE purchase_documents DROP COLUMN IF EXISTS doc_number')
