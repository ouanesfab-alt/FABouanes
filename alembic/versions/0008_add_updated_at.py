"""Add updated_at triggers

Revision ID: 0008_add_updated_at
Revises: 0007_fix_timestamp_types
Create Date: 2026-05-17 20:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0008_add_updated_at'
down_revision = '0007_fix_timestamp_types'
branch_labels = None
depends_on = None

tables_to_add_updated_at = [
    'clients',
    'suppliers',
    'raw_materials',
    'finished_products',
    'sales',
    'raw_sales',
    'purchases',
    'payments',
    'sale_documents',
    'purchase_documents'
]

def upgrade() -> None:
    # 1. Create the generic updated_at function if not exists
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 2. Add column and create trigger for each table
    for table in tables_to_add_updated_at:
        # Add column
        op.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()')
        
        # Drop trigger if exists (to be safe and idempotent)
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')
        
        # Create trigger
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON "{table}"
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """)

def downgrade() -> None:
    for table in tables_to_add_updated_at:
        # Drop trigger
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')
        # Drop column
        op.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS updated_at')
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
