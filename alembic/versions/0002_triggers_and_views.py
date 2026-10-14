"""0002_triggers_and_views - Dedicated migration for SQL views, triggers, and consistency functions.

Revision ID: 0002_triggers_and_views
Revises: 0001_initial_schema
Create Date: 2026-10-14 12:15:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_triggers_and_views"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

tables_to_add_updated_at = [
    "clients",
    "suppliers",
    "raw_materials",
    "finished_products",
    "sales",
    "raw_sales",
    "purchases",
    "payments",
    "sale_documents",
    "purchase_documents",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # 1. updated_at triggers and functions
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
            EXECUTE FUNCTION set_updated_at();
        """)

    # 2. Check constraint on users.role
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
            EXECUTE 'ALTER TABLE users DROP CONSTRAINT IF EXISTS ' || quote_ident(r.constraint_name);
        END LOOP;
    END $$;
    """)
    try:
        op.create_check_constraint(
            "chk_users_role",
            "users",
            sa.text("role IN ('admin', 'operator', 'manager')"),
        )
    except Exception:
        pass

    # 3. Client history synchronization triggers
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

            v_montant_achat := 0;
            v_montant_verse := NEW.amount;
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
                montant_achat = 0,
                montant_verse = NEW.amount,
                client_id = NEW.client_id
            WHERE payment_id = NEW.id;
        ELSIF TG_OP = 'DELETE' THEN
            DELETE FROM client_history WHERE payment_id = OLD.id;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_sync_payment_to_history ON payments;
    CREATE TRIGGER trg_sync_payment_to_history
    AFTER INSERT OR UPDATE OR DELETE ON payments
    FOR EACH ROW EXECUTE FUNCTION sync_payment_to_client_history();
    """)

    # 4. Materialized View mv_client_balances
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_client_balances CASCADE;")

    op.execute("""
    CREATE MATERIALIZED VIEW mv_client_balances AS
    SELECT 
        c.id AS client_id,
        c.name,
        c.opening_credit
            + COALESCE(s_finished.total, 0)
            + COALESCE(s_raw.total, 0)
            - COALESCE(p_versement.total, 0)
            - COALESCE(p_avance.total, 0) AS balance
    FROM clients c
    LEFT JOIN (SELECT client_id, SUM(total) AS total FROM sales WHERE sale_type='credit' GROUP BY client_id) s_finished ON s_finished.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(total) AS total FROM raw_sales WHERE sale_type='credit' GROUP BY client_id) s_raw ON s_raw.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='versement' GROUP BY client_id) p_versement ON p_versement.client_id = c.id
    LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='avance' GROUP BY client_id) p_avance ON p_avance.client_id = c.id;
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_client_balances_id ON mv_client_balances(client_id);")

    # 5. View clients_with_stats
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
    SELECT c.id,
           c.name,
           c.phone,
           c.address,
           c.notes,
           c.opening_credit,
           c.created_at,
           c.updated_at,
           COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
           COALESCE(ft.credit_total, 0) + COALESCE(rt.credit_total, 0) AS total_credit_sales,
           COALESCE(pt.versements, 0) AS total_versements,
           COALESCE(pt.avances, 0) AS total_avances,
           c.opening_credit
               + COALESCE(ft.credit_total, 0)
               + COALESCE(rt.credit_total, 0)
               - COALESCE(pt.versements, 0)
               - COALESCE(pt.avances, 0) AS current_balance
    FROM clients c
    LEFT JOIN finished_totals ft ON ft.client_id = c.id
    LEFT JOIN raw_totals rt ON rt.client_id = c.id
    LEFT JOIN payment_totals pt ON pt.client_id = c.id;
    """)


def downgrade() -> None:
    pass
