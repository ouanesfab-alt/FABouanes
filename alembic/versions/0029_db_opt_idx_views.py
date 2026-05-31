"""database optimization indexes and views

Revision ID: 0029_db_opt_idx_views
Revises: None
Create Date: 2026-05-25 15:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0029_db_opt_idx_views'
down_revision = None
branch_labels = None
depends_on = None

columns_to_fix = [
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # A. Ensure missing columns are added first
    # 1. raw_sales: custom_item_name TEXT
    columns_raw_sales = [c['name'] for c in inspector.get_columns('raw_sales')]
    if 'custom_item_name' not in columns_raw_sales:
        op.add_column('raw_sales', sa.Column('custom_item_name', sa.Text(), nullable=True))

    # 2. purchases: custom_item_name TEXT
    columns_purchases = [c['name'] for c in inspector.get_columns('purchases')]
    if 'custom_item_name' not in columns_purchases:
        op.add_column('purchases', sa.Column('custom_item_name', sa.Text(), nullable=True))

    # 3. activity_logs: user_id INTEGER, old_value TEXT, new_value TEXT, ip_address TEXT
    columns_activity_logs = [c['name'] for c in inspector.get_columns('activity_logs')]
    if 'user_id' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('user_id', sa.Integer(), nullable=True))
    if 'old_value' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('old_value', sa.Text(), nullable=True))
    if 'new_value' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('new_value', sa.Text(), nullable=True))
    if 'ip_address' not in columns_activity_logs:
        op.add_column('activity_logs', sa.Column('ip_address', sa.Text(), nullable=True))

    # B. Type conversions
    # 1. Convert production_batches.production_date to DATE
    op.execute("ALTER TABLE production_batches ALTER COLUMN production_date TYPE DATE USING production_date::DATE")

    # 2. Convert users must_change_password and is_active from INTEGER to BOOLEAN
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password TYPE BOOLEAN USING (must_change_password::int != 0)")
    op.execute("ALTER TABLE users ALTER COLUMN must_change_password SET DEFAULT FALSE")
    
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN is_active TYPE BOOLEAN USING (is_active::int != 0)")
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE")

    # C. Alter all financial and quantity columns to NUMERIC(15, 4)
    for table, col in columns_to_fix:
        cols_in_table = [c['name'] for c in inspector.get_columns(table)]
        if col in cols_in_table:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE NUMERIC(15,4) USING "{col}"::numeric')

    # D. Add updated_at trigger function and triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
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
    for table in tables_to_add_updated_at:
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON "{table}"
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at()
        """)

    # E. Re-create users role check constraint to include 'manager'
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

    # 3. Create table client_history
    op.execute("""
        CREATE TABLE IF NOT EXISTS client_history (
            id             SERIAL PRIMARY KEY,
            client_id      INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            operation_date DATE NOT NULL,
            designation    TEXT NOT NULL DEFAULT '',
            montant_achat  NUMERIC(15,4) NOT NULL DEFAULT 0,
            montant_verse  NUMERIC(15,4) NOT NULL DEFAULT 0,
            solde_cumule   NUMERIC(15,4) NOT NULL DEFAULT 0,
            ordre_import   INTEGER NOT NULL DEFAULT 0,
            source         TEXT NOT NULL DEFAULT 'import_excel',
            sale_id        INTEGER,
            raw_sale_id    INTEGER,
            payment_id     INTEGER,
            created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ch_client_id ON client_history(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ch_date ON client_history(client_id, operation_date)")

    # 4. Trigger functions and triggers for client history auto-sync
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_sale_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE sale_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, sale_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.sale_date,
                    (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                    NEW.total,
                    NEW.amount_paid,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                IF EXISTS(SELECT 1 FROM client_history WHERE sale_id = NEW.id) THEN
                    UPDATE client_history
                    SET operation_date = NEW.sale_date,
                        designation = (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                        montant_achat = NEW.total,
                        montant_verse = NEW.amount_paid,
                        client_id = NEW.client_id
                    WHERE sale_id = NEW.id;
                ELSE
                    SELECT COALESCE(
                        (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                        (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                        0
                    ) INTO v_prev_solde;

                    v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                    INSERT INTO client_history (
                        client_id, operation_date, designation,
                        montant_achat, montant_verse, solde_cumule,
                        ordre_import, source, sale_id, created_at
                    ) VALUES (
                        NEW.client_id,
                        NEW.sale_date,
                        (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                        NEW.total,
                        NEW.amount_paid,
                        v_solde,
                        (SELECT COALESCE(MAX(ordre_import), -1) + 1
                         FROM client_history WHERE client_id = NEW.client_id),
                        'app',
                        NEW.id,
                        NEW.created_at
                    );
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_sale_to_history ON sales;
        CREATE TRIGGER trg_sync_sale_to_history
        AFTER INSERT OR UPDATE OR DELETE ON sales
        FOR EACH ROW EXECUTE FUNCTION sync_sale_to_client_history();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION sync_raw_sale_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE raw_sale_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, raw_sale_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.sale_date,
                    (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                    NEW.total,
                    NEW.amount_paid,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                IF EXISTS(SELECT 1 FROM client_history WHERE raw_sale_id = NEW.id) THEN
                    UPDATE client_history
                    SET operation_date = NEW.sale_date,
                        designation = (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                        montant_achat = NEW.total,
                        montant_verse = NEW.amount_paid,
                        client_id = NEW.client_id
                    WHERE raw_sale_id = NEW.id;
                ELSE
                    SELECT COALESCE(
                        (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                        (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                        0
                    ) INTO v_prev_solde;

                    v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                    INSERT INTO client_history (
                        client_id, operation_date, designation,
                        montant_achat, montant_verse, solde_cumule,
                        ordre_import, source, raw_sale_id, created_at
                    ) VALUES (
                        NEW.client_id,
                        NEW.sale_date,
                        (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                        NEW.total,
                        NEW.amount_paid,
                        v_solde,
                        (SELECT COALESCE(MAX(ordre_import), -1) + 1
                         FROM client_history WHERE client_id = NEW.client_id),
                        'app',
                        NEW.id,
                        NEW.created_at
                    );
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE raw_sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_raw_sale_to_history ON raw_sales;
        CREATE TRIGGER trg_sync_raw_sale_to_history
        AFTER INSERT OR UPDATE OR DELETE ON raw_sales
        FOR EACH ROW EXECUTE FUNCTION sync_raw_sale_to_client_history();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION sync_payment_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
            v_montant_achat NUMERIC(15,4);
            v_montant_verse NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE payment_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_montant_achat := CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END;
                v_montant_verse := CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END;
                v_solde := v_prev_solde + v_montant_achat - v_montant_verse;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, payment_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.payment_date,
                    CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lié à la vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lié à la vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    v_montant_achat,
                    v_montant_verse,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                UPDATE client_history
                SET operation_date = NEW.payment_date,
                    designation = CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lié à la vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lié à la vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    montant_achat = CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END,
                    montant_verse = CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END,
                    client_id = NEW.client_id
                WHERE payment_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE payment_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_payment_to_history ON payments;
        CREATE TRIGGER trg_sync_payment_to_history
        AFTER INSERT OR UPDATE OR DELETE ON payments
        FOR EACH ROW EXECUTE FUNCTION sync_payment_to_client_history();
    """)

    # 5. Create views & materialized views
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

    # 6. Ensure stock alerts table exists and alter finished_products
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

    # 7. Create all optimization & search indexes
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
    pass
