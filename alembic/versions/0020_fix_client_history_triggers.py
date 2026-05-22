"""Fix client history triggers to calculate cumulative balance

Revision ID: 0020_fix_client_history_triggers
Revises: 0019_add_client_history
Create Date: 2026-05-22 12:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision = '0020_fix_client_history_triggers'
down_revision = '0019_add_client_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update sync_sale_to_client_history function
    # Calcule le solde courant au moment de l'insert au lieu d'insérer 0
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_sale_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(12,2);
            v_solde NUMERIC(12,2);
        BEGIN
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
                UPDATE client_history
                SET operation_date = NEW.sale_date,
                    designation = (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                    montant_achat = NEW.total,
                    montant_verse = NEW.amount_paid,
                    client_id = NEW.client_id
                WHERE sale_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 2. Update sync_raw_sale_to_client_history function
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_raw_sale_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(12,2);
            v_solde NUMERIC(12,2);
        BEGIN
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
                UPDATE client_history
                SET operation_date = NEW.sale_date,
                    designation = (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                    montant_achat = NEW.total,
                    montant_verse = NEW.amount_paid,
                    client_id = NEW.client_id
                WHERE raw_sale_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE raw_sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Update sync_payment_to_client_history function
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_payment_to_client_history()
        RETURNS TRIGGER AS $$
        DECLARE
            v_prev_solde NUMERIC(12,2);
            v_solde NUMERIC(12,2);
            v_montant_achat NUMERIC(12,2);
            v_montant_verse NUMERIC(12,2);
        BEGIN
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
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lie a vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lie a vente produit'
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
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Restaure les anciennes fonctions de la version 0019 (solde_cumule=0 pour source='app')
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
