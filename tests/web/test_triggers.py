"""
Tests des triggers PostgreSQL : sync_sale/raw_sale/payment → client_history.
Ces triggers constituent la Zone 2 de l'historique client (opérations via l'appli).
"""
# Choix importants :
# 1. Utilisation de requêtes SQL brutes INSERT/UPDATE/DELETE pour déclencher et valider directement le comportement des triggers PostgreSQL.
# 2. Nettoyage méticuleux des tables après chaque test pour maintenir l'indépendance et la propreté de la base de données.

from __future__ import annotations
import pytest
from app.core.db_access import execute_db, query_db


@pytest.fixture(autouse=True)
def clean_db():
    yield
    execute_db("DELETE FROM client_history")
    execute_db("DELETE FROM payments")
    execute_db("DELETE FROM sales")
    execute_db("DELETE FROM raw_sales")
    execute_db("DELETE FROM clients WHERE name LIKE 'Trigger%'")


class TestSaleTrigger:
    def test_sale_creates_client_history_row(self, client):
        """Un INSERT dans sales doit créer automatiquement une ligne dans client_history."""
        # 1. Créer un client de test
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 1', 100.0)")

        # Obtenir un produit
        prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
        prod_id = int(prod["id"])

        # 2. Créer une vente pour ce client
        sale_id = execute_db(
            """
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
            VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 200.0, 800.0, '2026-05-01')
            """,
            (client_id, prod_id)
        )

        # 3. Vérifier que client_history contient une ligne source='app'
        rows = query_db("SELECT * FROM client_history WHERE client_id = %s", (client_id,))
        assert len(rows) == 1
        row = rows[0]
        assert row["source"] == "app"
        assert row["sale_id"] == sale_id

        # 4. Vérifier montant_achat, montant_verse, solde_cumule
        assert float(row["montant_achat"]) == 1000.0
        assert float(row["montant_verse"]) == 200.0
        # solde_cumule = opening_credit (100.0) + total (1000.0) - amount_paid (200.0) = 900.0
        assert float(row["solde_cumule"]) == 900.0

    def test_sale_history_solde_cumule_correct(self, client):
        """Le solde_cumule dans client_history doit être total - amount_paid."""
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 2', 0.0)")
        prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
        prod_id = int(prod["id"])

        execute_db(
            """
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
            VALUES (%s, %s, 5.0, 'kg', 100.0, 500.0, 'credit', 100.0, 400.0, '2026-05-01')
            """,
            (client_id, prod_id)
        )

        rows = query_db("SELECT * FROM client_history WHERE client_id = %s ORDER BY id DESC", (client_id,))
        assert len(rows) == 1
        assert float(rows[0]["solde_cumule"]) == 400.0

    def test_raw_sale_creates_history(self, client):
        """Même test pour raw_sales."""
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 3', 50.0)")
        raw = query_db("SELECT id FROM raw_materials LIMIT 1", one=True)
        raw_id = int(raw["id"])

        raw_sale_id = execute_db(
            """
            INSERT INTO raw_sales (client_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
            VALUES (%s, %s, 2.0, 'kg', 50.0, 100.0, 'credit', 30.0, 70.0, '2026-05-01')
            """,
            (client_id, raw_id)
        )

        rows = query_db("SELECT * FROM client_history WHERE client_id = %s", (client_id,))
        assert len(rows) == 1
        row = rows[0]
        assert row["source"] == "app"
        assert row["raw_sale_id"] == raw_sale_id
        assert float(row["montant_achat"]) == 100.0
        assert float(row["montant_verse"]) == 30.0
        # solde_cumule = 50.0 + 100.0 - 30.0 = 120.0
        assert float(row["solde_cumule"]) == 120.0

    def test_payment_creates_history(self, client):
        """Un versement doit créer une ligne avec montant_verse rempli."""
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 4', 300.0)")

        # Créer un paiement de type versement
        payment_id = execute_db(
            """
            INSERT INTO payments (client_id, amount, payment_type, payment_date, notes)
            VALUES (%s, 100.0, 'versement', '2026-05-01', 'Versement Test')
            """,
            (client_id,)
        )

        rows = query_db("SELECT * FROM client_history WHERE client_id = %s", (client_id,))
        assert len(rows) == 1
        row = rows[0]
        assert row["source"] == "app"
        assert row["payment_id"] == payment_id
        assert float(row["montant_achat"]) == 0.0
        assert float(row["montant_verse"]) == 100.0
        # solde_cumule = opening_credit (300.0) + 0 - 100.0 = 200.0
        assert float(row["solde_cumule"]) == 200.0

    def test_multiple_operations_accumulate_correctly(self, client):
        """Après 3 opérations, le solde cumulé doit être cohérent."""
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 5', 10.0)")
        prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
        prod_id = int(prod["id"])

        # Opération 1: Vente (total=100, versement=20) -> Solde attendu: 10 + 100 - 20 = 90
        execute_db(
            """
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
            VALUES (%s, %s, 1.0, 'kg', 100.0, 100.0, 'credit', 20.0, 80.0, '2026-05-01')
            """,
            (client_id, prod_id)
        )

        # Opération 2: Paiement (versement=50) -> Solde attendu: 90 - 50 = 40
        execute_db(
            """
            INSERT INTO payments (client_id, amount, payment_type, payment_date, notes)
            VALUES (%s, 50.0, 'versement', '2026-05-02', 'Versement 2')
            """,
            (client_id,)
        )

        # Opération 3: Paiement (avance=30) -> Solde attendu: 40 + 30 = 70
        execute_db(
            """
            INSERT INTO payments (client_id, amount, payment_type, payment_date, notes)
            VALUES (%s, 30.0, 'avance', '2026-05-03', 'Avance 3')
            """,
            (client_id,)
        )

        rows = query_db("SELECT * FROM client_history WHERE client_id = %s ORDER BY created_at ASC, id ASC", (client_id,))
        assert len(rows) == 3
        assert float(rows[0]["solde_cumule"]) == 90.0
        assert float(rows[1]["solde_cumule"]) == 40.0
        assert float(rows[2]["solde_cumule"]) == 70.0

    def test_source_is_app_not_import_excel(self, client):
        """Les lignes créées par trigger doivent avoir source='app'."""
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Trigger Test Client 6', 0.0)")
        execute_db(
            """
            INSERT INTO payments (client_id, amount, payment_type, payment_date, notes)
            VALUES (%s, 50.0, 'versement', '2026-05-01', 'Test')
            """,
            (client_id,)
        )
        row = query_db("SELECT source FROM client_history WHERE client_id = %s", (client_id,), one=True)
        assert row["source"] == "app"
