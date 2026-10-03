"""fix clients_with_stats updated_at, advances sign, trigger and staging locked_at

Revision ID: 0040_fix_stats_advances
Revises: 0039_perf_indexes_v2_3
Create Date: 2026-10-03 02:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0040_fix_stats_advances"
down_revision = "0039_perf_indexes_v2_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ensure staging tables have locked_at column for safe worker job acquisition
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "offline_sales_staging" in tables:
        cols = [c["name"] for c in inspector.get_columns("offline_sales_staging")]
        if "locked_at" not in cols:
            op.add_column("offline_sales_staging", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))

    if "offline_payments_staging" in tables:
        cols = [c["name"] for c in inspector.get_columns("offline_payments_staging")]
        if "locked_at" not in cols:
            op.add_column("offline_payments_staging", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Update view clients_with_stats to include c.updated_at and correct advance sign
    op.execute("DROP VIEW IF EXISTS clients_with_stats CASCADE")
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
    SELECT c.id, c.name, c.phone, c.address, c.notes, c.opening_credit, c.created_at, c.updated_at, c.search_vector,
           c.opening_credit
           + COALESCE(ft.credit_total, 0)
           + COALESCE(rt.credit_total, 0)
           - COALESCE(pt.versements, 0)
           - COALESCE(pt.avances, 0) AS current_debt,
           c.opening_credit
           + COALESCE(ft.credit_total, 0)
           + COALESCE(rt.credit_total, 0)
           - COALESCE(pt.versements, 0)
           - COALESCE(pt.avances, 0) AS current_balance,
           COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
           COALESCE(pt.versements, 0) AS total_payments
    FROM clients c
    LEFT JOIN finished_totals ft ON ft.client_id = c.id
    LEFT JOIN raw_totals rt ON rt.client_id = c.id
    LEFT JOIN payment_totals pt ON pt.client_id = c.id;
    """)

    # 3. Update sync_payment_to_client_history trigger function
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
    """)

    # 4. Correct past client_history rows where avance was recorded as purchase
    if "client_history" in tables and "payments" in tables:
        op.execute("""
        UPDATE client_history ch
        SET montant_verse = ch.montant_achat,
            montant_achat = 0
        FROM payments p
        WHERE ch.payment_id = p.id
          AND p.payment_type = 'avance'
          AND ch.montant_achat > 0
          AND ch.montant_verse = 0;
        """)


def downgrade() -> None:
    pass
