"""Add client history table and triggers for auto-syncing app operations

Revision ID: 0019_add_client_history
Revises: 0018_client_balance_view
Create Date: 2026-05-20 00:20:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0019_add_client_history'
down_revision = '0018_client_balance_view'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create table client_history
    op.execute("""
        CREATE TABLE IF NOT EXISTS client_history (
            id             SERIAL PRIMARY KEY,
            client_id      INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            operation_date DATE NOT NULL,
            designation    TEXT NOT NULL DEFAULT '',
            montant_achat  NUMERIC(12,2) NOT NULL DEFAULT 0,
            montant_verse  NUMERIC(12,2) NOT NULL DEFAULT 0,
            solde_cumule   NUMERIC(12,2) NOT NULL DEFAULT 0,
            ordre_import   INTEGER NOT NULL DEFAULT 0,
            source         TEXT NOT NULL DEFAULT 'import_excel',
            sale_id        INTEGER,
            raw_sale_id    INTEGER,
            payment_id     INTEGER,
            created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_ch_client_id ON client_history(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ch_date ON client_history(client_id, operation_date)")
    
    # 3. Trigger for sales
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_sale_to_client_history()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, sale_id, created_at)
                SELECT NEW.client_id, NEW.sale_date, fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, ''), NEW.total, 0, 'app', NEW.id, NEW.created_at
                FROM finished_products fp WHERE fp.id = NEW.finished_product_id;
            ELSIF TG_OP = 'UPDATE' THEN
                UPDATE client_history
                SET operation_date = NEW.sale_date,
                    designation = (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                    montant_achat = NEW.total,
                    client_id = NEW.client_id
                WHERE sale_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE sale_id = OLD.id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_sale_to_history ON sales;
        CREATE TRIGGER trg_sync_sale_to_history
        AFTER INSERT OR UPDATE OR DELETE ON sales
        FOR EACH ROW EXECUTE FUNCTION sync_sale_to_client_history();
    """)
    
    # Trigger for raw_sales
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_raw_sale_to_client_history()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, raw_sale_id, created_at)
                SELECT NEW.client_id, NEW.sale_date, COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, ''), NEW.total, 0, 'app', NEW.id, NEW.created_at
                FROM raw_materials r WHERE r.id = NEW.raw_material_id;
            ELSIF TG_OP = 'UPDATE' THEN
                UPDATE client_history
                SET operation_date = NEW.sale_date,
                    designation = (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                    montant_achat = NEW.total,
                    client_id = NEW.client_id
                WHERE raw_sale_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE raw_sale_id = OLD.id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_raw_sale_to_history ON raw_sales;
        CREATE TRIGGER trg_sync_raw_sale_to_history
        AFTER INSERT OR UPDATE OR DELETE ON raw_sales
        FOR EACH ROW EXECUTE FUNCTION sync_raw_sale_to_client_history();
    """)

    # Trigger for payments
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_payment_to_client_history()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, payment_id, created_at)
                VALUES (
                    NEW.client_id,
                    NEW.payment_date,
                    CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lie a vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lie a vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END,
                    CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END,
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                UPDATE client_history
                SET operation_date = NEW.payment_date,
                    designation = CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lie a vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lie a vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    montant_achat = CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END,
                    montant_verse = CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END,
                    client_id = NEW.client_id
                WHERE payment_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE payment_id = OLD.id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_payment_to_history ON payments;
        CREATE TRIGGER trg_sync_payment_to_history
        AFTER INSERT OR UPDATE OR DELETE ON payments
        FOR EACH ROW EXECUTE FUNCTION sync_payment_to_client_history();
    """)
    
    # 4. Copy existing data into client_history
    op.execute("""
        INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, sale_id, created_at)
        SELECT s.client_id, s.sale_date, fp.name || ' - ' || s.quantity || ' ' || COALESCE(s.unit, ''), s.total, 0, 'app', s.id, s.created_at
        FROM sales s
        JOIN finished_products fp ON fp.id = s.finished_product_id
        WHERE s.client_id IS NOT NULL;
    """)
    
    op.execute("""
        INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, raw_sale_id, created_at)
        SELECT rs.client_id, rs.sale_date, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) || ' (matière première) - ' || rs.quantity || ' ' || COALESCE(rs.unit, ''), rs.total, 0, 'app', rs.id, rs.created_at
        FROM raw_sales rs
        JOIN raw_materials r ON r.id = rs.raw_material_id
        WHERE rs.client_id IS NOT NULL;
    """)
    
    op.execute("""
        INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, source, payment_id, created_at)
        SELECT p.client_id, p.payment_date,
               CASE
                   WHEN p.sale_kind = 'raw' THEN 'Versement lie a vente matière'
                   WHEN p.sale_kind = 'finished' THEN 'Versement lie a vente produit'
                   ELSE COALESCE(NULLIF(p.notes,''), CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
               END,
               CASE WHEN p.payment_type='avance' THEN p.amount ELSE 0 END,
               CASE WHEN p.payment_type='versement' THEN p.amount ELSE 0 END,
               'app',
               p.id,
               p.created_at
        FROM payments p
        WHERE p.client_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_sale_to_history ON sales")
    op.execute("DROP FUNCTION IF EXISTS sync_sale_to_client_history")
    
    op.execute("DROP TRIGGER IF EXISTS trg_sync_raw_sale_to_history ON raw_sales")
    op.execute("DROP FUNCTION IF EXISTS sync_raw_sale_to_client_history")
    
    op.execute("DROP TRIGGER IF EXISTS trg_sync_payment_to_history ON payments")
    op.execute("DROP FUNCTION IF EXISTS sync_payment_to_client_history")

    op.execute("DROP TABLE IF EXISTS client_history")
