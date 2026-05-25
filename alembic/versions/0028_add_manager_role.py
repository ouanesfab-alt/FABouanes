"""add manager role check constraint

Revision ID: 0028_add_manager_role
Revises: 0027_add_stock_alerts
Create Date: 2026-05-24 18:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0028_add_manager_role'
down_revision = '0027_add_stock_alerts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safely find and drop any CHECK constraint on the role column of users table
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
    # Add new constraint allowing admin, operator, and manager roles
    op.create_check_constraint(
        "chk_users_role",
        "users",
        sa.text("role IN ('admin', 'operator', 'manager')")
    )


def downgrade() -> None:
    # Revert role CHECK constraint back to admin and operator only
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
        sa.text("role IN ('admin', 'operator')")
    )
