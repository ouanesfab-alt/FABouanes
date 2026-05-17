"""Add FTS to PostgreSQL

Revision ID: 0012_add_fts_postgresql
Revises: 0009_add_document_numbers
Create Date: 2026-05-17 20:40:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0012_add_fts_postgresql'
down_revision = '0009_add_document_numbers'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add search_vector column to clients
    op.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS search_vector tsvector')
    
    # 2. Create GIN index on search_vector
    op.execute('CREATE INDEX IF NOT EXISTS idx_clients_fts ON clients USING GIN(search_vector)')
    
    # 3. Create or replace trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_clients_search_vector() RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('french',
                COALESCE(NEW.name,'') || ' ' || COALESCE(NEW.phone,'') || ' ' || COALESCE(NEW.address,''));
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)
    
    # 4. Create trigger
    op.execute('DROP TRIGGER IF EXISTS trg_clients_fts ON clients')
    op.execute("""
        CREATE TRIGGER trg_clients_fts BEFORE INSERT OR UPDATE ON clients
        FOR EACH ROW EXECUTE FUNCTION update_clients_search_vector()
    """)
    
    # 5. Populate search_vector for existing clients
    op.execute("""
        UPDATE clients 
        SET search_vector = to_tsvector('french', 
            COALESCE(name,'') || ' ' || COALESCE(phone,'') || ' ' || COALESCE(address,''))
    """)

def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS trg_clients_fts ON clients')
    op.execute('DROP FUNCTION IF EXISTS update_clients_search_vector()')
    op.execute('DROP INDEX IF EXISTS idx_clients_fts')
    op.execute('ALTER TABLE clients DROP COLUMN IF EXISTS search_vector')
