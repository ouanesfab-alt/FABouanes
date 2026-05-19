"""Add materialized view for client balances

Revision ID: 0018_client_balance_view
Revises: 0017_fix_column_types
Create Date: 2026-05-20 00:16:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = '0018_client_balance_view'
down_revision = '0017_fix_column_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create materialized view for precomputed client balances
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_client_balances AS
    SELECT 
        c.id AS client_id,
        c.name,
        c.opening_credit
            + COALESCE(s_finished.total, 0)
            + COALESCE(s_raw.total, 0)
            - COALESCE(p_versement.total, 0)
            + COALESCE(p_avance.total, 0) AS balance
    FROM clients c
    LEFT JOIN (SELECT client_id, SUM(total) AS total FROM sales WHERE sale_type='credit' GROUP BY client_id) s_finished ON s_finished.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(total) AS total FROM raw_sales WHERE sale_type='credit' GROUP BY client_id) s_raw ON s_raw.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='versement' GROUP BY client_id) p_versement ON p_versement.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='avance' GROUP BY client_id) p_avance ON p_avance.client_id = c.id;
    """)

    # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_client_balances_id ON mv_client_balances(client_id)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances")
