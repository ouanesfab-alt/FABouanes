"""Fix timestamp types

Revision ID: 0007_fix_timestamp_types
Revises: 0006_add_document_fk
Create Date: 2026-05-17 20:25:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0007_fix_timestamp_types'
down_revision = '0006_add_document_fk'
branch_labels = None
depends_on = None

# List of columns to convert to TIMESTAMPTZ
# Format: (table, column, is_nullable)
timestamp_columns = [
    # app/core/schema/core.py
    ('users', 'last_login_at', True),
    ('users', 'last_password_change_at', True),
    ('users', 'created_at', False),
    
    ('app_settings', 'updated_at', False),
    
    ('activity_logs', 'created_at', False),
    ('error_logs', 'created_at', False),
    ('system_logs', 'created_at', False),
    ('performance_logs', 'created_at', False),
    ('audit_logs', 'created_at', False),
    
    ('backup_jobs', 'created_at', False),
    ('backup_jobs', 'started_at', True),
    ('backup_jobs', 'finished_at', True),
    
    ('backup_runs', 'started_at', True),
    ('backup_runs', 'finished_at', True),
    
    ('api_refresh_tokens', 'expires_at', False),
    ('api_refresh_tokens', 'revoked_at', True),
    ('api_refresh_tokens', 'last_used_at', True),
    ('api_refresh_tokens', 'created_at', False),
    
    # app/core/schema/contacts.py
    ('clients', 'created_at', False),
    ('suppliers', 'created_at', False),
    ('imported_client_history', 'created_at', False),
    
    # app/core/schema/operations.py
    ('purchase_documents', 'created_at', False),
    ('sale_documents', 'created_at', False),
    ('purchases', 'created_at', False),
    ('sales', 'created_at', False),
    ('raw_sales', 'created_at', False),
    ('payments', 'created_at', False),
    
    # app/core/schema/production.py
    ('saved_recipes', 'created_at', False),
    ('saved_recipes', 'updated_at', False),
]

def upgrade() -> None:
    bind = op.get_bind()
    for table, col, nullable in timestamp_columns:
        # Check current type in database
        res = bind.execute(
            sa.text("SELECT data_type FROM information_schema.columns WHERE table_name = :table AND column_name = :col"),
            {"table": table, "col": col}
        ).fetchone()
        
        current_type = res[0].lower() if res else ""
        if not current_type:
            continue
            
        if "timestamp" in current_type:
            # Already a timestamp, just ensure it's TIMESTAMPTZ
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TIMESTAMPTZ')
            if not nullable:
                op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" SET DEFAULT NOW()')
        else:
            # Text type: convert with USING
            if nullable:
                op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TIMESTAMPTZ USING (CASE WHEN TRIM(BOTH FROM COALESCE("{col}", \'\')) ~ \'^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}\' THEN TRIM(BOTH FROM "{col}")::timestamptz ELSE NULL END)')
                op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" DROP DEFAULT')
            else:
                op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TIMESTAMPTZ USING COALESCE(CASE WHEN TRIM(BOTH FROM COALESCE("{col}", \'\')) ~ \'^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}\' THEN TRIM(BOTH FROM "{col}")::timestamptz ELSE NULL END, NOW())')
                op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" SET DEFAULT NOW()')

def downgrade() -> None:
    for table, col, nullable in timestamp_columns:
        if nullable:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::text')
        else:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::text')
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" SET DEFAULT CURRENT_TIMESTAMP::text')
