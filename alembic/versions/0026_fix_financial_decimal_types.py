"""Fix financial decimal types to NUMERIC(15, 4)

Revision ID: 0026_fix_financial_decimal_types
Revises: 0025_transaction_performance_idx
Create Date: 2026-05-24 16:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0026_fix_financial_decimal_types'
down_revision = '0025_transaction_performance_idx'
branch_labels = None
depends_on = None

columns_to_fix = [
    # (table, column)
    ('clients', 'opening_credit'),
    ('imported_client_history', 'debit_amount'),
    ('imported_client_history', 'credit_amount'),
    ('imported_client_history', 'running_balance'),
    ('raw_materials', 'stock_qty'),
    ('raw_materials', 'avg_cost'),
    ('raw_materials', 'sale_price'),
    ('raw_materials', 'alert_threshold'),
    ('raw_materials', 'threshold_qty'),
    ('finished_products', 'stock_qty'),
    ('finished_products', 'sale_price'),
    ('finished_products', 'avg_cost'),
    ('stock_movements', 'quantity'),
    ('stock_movements', 'stock_before'),
    ('stock_movements', 'stock_after'),
    ('purchase_documents', 'total'),
    ('sale_documents', 'total'),
    ('sale_documents', 'amount_paid'),
    ('sale_documents', 'balance_due'),
    ('purchases', 'quantity'),
    ('purchases', 'unit_price'),
    ('purchases', 'total'),
    ('sales', 'quantity'),
    ('sales', 'unit_price'),
    ('sales', 'total'),
    ('sales', 'amount_paid'),
    ('sales', 'balance_due'),
    ('sales', 'cost_price_snapshot'),
    ('sales', 'profit_amount'),
    ('raw_sales', 'quantity'),
    ('raw_sales', 'unit_price'),
    ('raw_sales', 'total'),
    ('raw_sales', 'amount_paid'),
    ('raw_sales', 'balance_due'),
    ('raw_sales', 'cost_price_snapshot'),
    ('raw_sales', 'profit_amount'),
    ('payments', 'amount'),
    ('production_batches', 'output_quantity'),
    ('production_batches', 'production_cost'),
    ('production_batches', 'unit_cost'),
    ('production_batch_items', 'quantity'),
    ('production_batch_items', 'unit_cost_snapshot'),
    ('production_batch_items', 'line_cost'),
    ('saved_recipe_items', 'quantity'),
]

def upgrade() -> None:
    # Drop dependent views
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances CASCADE")

    # Alter the columns
    for table, col in columns_to_fix:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE NUMERIC(15,4) USING "{col}"::numeric')

    # Recreate materialized view
    op.execute("""
    CREATE MATERIALIZED VIEW mv_client_balances AS
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
    op.execute("CREATE UNIQUE INDEX idx_mv_client_balances_id ON mv_client_balances(client_id)")

    # Recreate normal view
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
    # Drop dependent views
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances CASCADE")

    # Alter the columns back
    for table, col in columns_to_fix:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE NUMERIC(14,2) USING ROUND("{col}"::numeric, 2)')

    # Recreate materialized view
    op.execute("""
    CREATE MATERIALIZED VIEW mv_client_balances AS
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
    op.execute("CREATE UNIQUE INDEX idx_mv_client_balances_id ON mv_client_balances(client_id)")

    # Recreate normal view
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
