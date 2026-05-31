"""database optimization - updated_at triggers and check constraints

Revision ID: 0031_updated_at_triggers
Revises: 0030_type_conversions
Create Date: 2026-05-25 17:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0031_updated_at_triggers'
down_revision = '0030_type_conversions'
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
    # 1. Add updated_at trigger function and triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in tables_to_add_updated_at:
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON "{table}"
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """)

    # 2. Re-create users role check constraint to include 'manager'
    op.execute("""
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'users'
              AND tc.constraint_type = 'CHECK'
              AND ccu.column_name = 'role'
        LOOP
            EXECUTE 'ALTER TABLE users DROP CONSTRAINT ' || quote_ident(r.constraint_name);
        END LOOP;
    END $$;
    """)
    op.create_check_constraint(
        "chk_users_role",
        "users",
        sa.text("role IN ('admin', 'operator', 'manager')")
    )


def downgrade() -> None:
    # 1. Drop updated_at triggers and function
    for table in tables_to_add_updated_at:
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    # 2. Revert role check constraint to basic admin/operator/manager if needed
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_role")
    op.create_check_constraint(
        "users_role_check",
        "users",
        sa.text("role IN ('admin', 'operator', 'manager')")
    )
