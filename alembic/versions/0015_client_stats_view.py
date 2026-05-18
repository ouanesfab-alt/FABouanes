"""Create clients_with_stats database VIEW

Revision ID: 0015_client_stats_view
Revises: 0014_migrate_operations_dates
Create Date: 2026-05-18 17:25:00.000000
"""
from __future__ import annotations

from alembic import op


revision = '0015_client_stats_view'
down_revision = '0014_migrate_operations_dates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the centralized view
    op.execute("""
    CREATE OR REPLACE VIEW clients_with_stats AS
    WITH finished_totals AS (
        SELECT client_id,
               SUM(total) AS total_sales,
               SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
        FROM sales
        WHERE client_id IS NOT NULL
        GROUP BY client_id
    ),
    raw_totals AS (
        SELECT client_id,
               SUM(total) AS total_sales,
               SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
        FROM raw_sales
        WHERE client_id IS NOT NULL
        GROUP BY client_id
    ),
    payment_totals AS (
        SELECT client_id,
               SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END) AS versements,
               SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END) AS avances
        FROM payments
        GROUP BY client_id
    )
    SELECT c.id, c.name, c.phone, c.address, c.notes, c.opening_credit, c.created_at, c.search_vector,
           c.opening_credit
           + COALESCE(ft.credit_total, 0)
           + COALESCE(rt.credit_total, 0)
           - COALESCE(pt.versements, 0)
           + COALESCE(pt.avances, 0) AS current_debt,
           c.opening_credit
           + COALESCE(ft.credit_total, 0)
           + COALESCE(rt.credit_total, 0)
           - COALESCE(pt.versements, 0)
           + COALESCE(pt.avances, 0) AS current_balance,
           COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
           COALESCE(pt.versements, 0) AS total_payments
    FROM clients c
    LEFT JOIN finished_totals ft ON ft.client_id = c.id
    LEFT JOIN raw_totals rt ON rt.client_id = c.id
    LEFT JOIN payment_totals pt ON pt.client_id = c.id;
    """)


def downgrade() -> None:
    # Drop view
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
