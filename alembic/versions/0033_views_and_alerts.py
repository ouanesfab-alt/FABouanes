"""database optimization - views, materialized views, alerts, and performance indexes

Revision ID: 0033_views_and_alerts
Revises: 0032_client_history
Create Date: 2026-05-25 19:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0033_views_and_alerts'
down_revision = '0032_client_history'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create views & materialized views
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances CASCADE")

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

    # 2. Ensure stock alerts table exists and alter finished_products
    op.execute("""
    CREATE TABLE IF NOT EXISTS stock_alerts (
        id BIGSERIAL PRIMARY KEY,
        product_type TEXT NOT NULL,
        product_id BIGINT NOT NULL,
        product_name TEXT NOT NULL,
        current_qty NUMERIC(15, 4) NOT NULL,
        threshold_qty NUMERIC(15, 4) NOT NULL,
        triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        acknowledged_at TIMESTAMPTZ
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_stock_alerts_product ON stock_alerts(product_type, product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stock_alerts_triggered_at ON stock_alerts(triggered_at)")
    
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('finished_products')]
    if 'alert_threshold' not in columns:
        op.add_column('finished_products', sa.Column('alert_threshold', sa.Numeric(precision=15, scale=4), server_default='0.0000', nullable=False))

    # 3. Create all optimization & search indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_covering_daily ON sales(sale_date, total, profit_amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_covering_daily ON raw_sales(sale_date, total, profit_amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_covering_daily ON payments(payment_date, amount)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_covering_daily ON purchases(purchase_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_material_date ON raw_sales(raw_material_id, sale_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_covering_type_date ON sales(sale_type, sale_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_covering_type_date ON raw_sales(sale_type, sale_date, total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_covering_type_date ON payments(payment_type, payment_date, amount)")

    op.execute("CREATE INDEX IF NOT EXISTS idx_client_history_search ON client_history(client_id, operation_date DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_reporting_composite ON sales(finished_product_id, sale_date DESC, client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_reporting_composite ON raw_sales(raw_material_id, sale_date DESC, client_id)")
    
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_client_date ON sales(client_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_sales_client_date ON raw_sales(client_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_client_date ON payments(client_id, payment_date DESC)")
    
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_materials_alert ON raw_materials(stock_qty, alert_threshold)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finished_products_alert ON finished_products(stock_qty)")
    
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(finished_product_id, sale_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_purchases_material ON purchases(raw_material_id, purchase_date DESC)")

    # FK constraints
    op.execute("ALTER TABLE sales DROP CONSTRAINT IF EXISTS fk_sales_document")
    op.execute("ALTER TABLE sales ADD CONSTRAINT fk_sales_document FOREIGN KEY (document_id) REFERENCES sale_documents(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE purchases DROP CONSTRAINT IF EXISTS fk_purchases_document")
    op.execute("ALTER TABLE purchases ADD CONSTRAINT fk_purchases_document FOREIGN KEY (document_id) REFERENCES purchase_documents(id) ON DELETE RESTRICT")


def downgrade() -> None:
    # Revert FKs
    op.execute("ALTER TABLE sales DROP CONSTRAINT IF EXISTS fk_sales_document")
    op.execute("ALTER TABLE purchases DROP CONSTRAINT IF EXISTS fk_purchases_document")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_purchases_material")
    op.execute("DROP INDEX IF EXISTS idx_sales_product")
    op.execute("DROP INDEX IF EXISTS idx_finished_products_alert")
    op.execute("DROP INDEX IF EXISTS idx_raw_materials_alert")
    op.execute("DROP INDEX IF EXISTS idx_payments_client_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_client_date")
    op.execute("DROP INDEX IF EXISTS idx_sales_client_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_reporting_composite")
    op.execute("DROP INDEX IF EXISTS idx_sales_reporting_composite")
    op.execute("DROP INDEX IF EXISTS idx_client_history_search")
    op.execute("DROP INDEX IF EXISTS idx_payments_covering_type_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_covering_type_date")
    op.execute("DROP INDEX IF EXISTS idx_sales_covering_type_date")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_material_date")
    op.execute("DROP INDEX IF EXISTS idx_purchases_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_payments_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_raw_sales_covering_daily")
    op.execute("DROP INDEX IF EXISTS idx_sales_covering_daily")

    # finished_products column
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('finished_products')]
    if 'alert_threshold' in columns:
        op.drop_column('finished_products', 'alert_threshold')

    # Drop stock alerts
    op.execute("DROP INDEX IF EXISTS idx_stock_alerts_triggered_at")
    op.execute("DROP INDEX IF EXISTS idx_stock_alerts_product")
    op.execute("DROP TABLE IF EXISTS stock_alerts")

    # Drop views
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances CASCADE")
