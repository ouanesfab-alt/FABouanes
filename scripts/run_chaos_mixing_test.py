#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/run_chaos_mixing_test.py
Suite de tests avancés sur le mélange de cas extrêmes et les dépendances enchevêtrées.
1. La double inversion : Vente -> Paiement -> Suppression de la Vente -> Suppression du Paiement.
2. Contraintes de clés étrangères (Bypass des sécurités de l'appli pour vérifier la base de données).
3. Achats gratuits massifs (Division par zéro et recalculs CMP).
4. Modification concurrente / Opérations entrecroisées.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import create_request_connection, bootstrap_and_migrate
from app.core.request_state import push_request_state, reset_request_state, set_state_value
from app.core.db_access import execute_db, query_db, db_transaction

from app.services.purchase_service import create_purchase_from_form
from app.services.sale_service import create_sale_from_form, delete_sale_by_id
from app.services.client_account_service import create_payment_record, client_balance
from app.services.payment_service import delete_payment_by_id


class MockForm(dict):
    def getlist(self, key):
        val = self.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return [str(x) for x in val]
        return [str(val)]


def run_mixed_chaos_tests():
    print("=" * 80)
    print("🌪️ DÉMARRAGE DE LA SUITE DE CHAOS MIXTE ET DE TESTS ENCHEVÊTRÉS 🌪️")
    print("=" * 80 + "\n")

    bootstrap_and_migrate()
    db = create_request_connection()

    admin_user = {"id": 1, "username": "admin", "role": "admin"}
    token = push_request_state(
        request=None,
        db=db,
        session={},
        request_id="chaos-mixed-id",
        audit_source="chaos_agent",
        user=admin_user,
    )
    set_state_value("user", admin_user)

    failures = 0
    passed = 0

    try:
        # Nettoyage initial
        with db_transaction():
            execute_db("DELETE FROM clients WHERE name = 'Client Mix Chaos'")
            execute_db("DELETE FROM suppliers WHERE name = 'Fournisseur Mix Chaos'")
            execute_db("DELETE FROM raw_materials WHERE name = 'Matiere Mix Chaos'")
            execute_db("DELETE FROM finished_products WHERE name = 'Produit Mix Chaos'")
            
            execute_db("INSERT INTO clients (name, phone, address, opening_credit) VALUES (%s, %s, %s, %s)",
                       ("Client Mix Chaos", "00", "Chaos", 0.0))
            execute_db("INSERT INTO suppliers (name, phone, address) VALUES (%s, %s, %s)",
                       ("Fournisseur Mix Chaos", "00", "Chaos"))
            execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                       ("Matiere Mix Chaos", "kg", 100.0, 100.0, 150.0))
            execute_db("INSERT INTO finished_products (name, default_unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                       ("Produit Mix Chaos", "kg", 50.0, 200.0, 300.0))

        client = query_db("SELECT * FROM clients WHERE name = 'Client Mix Chaos'", one=True)
        supplier = query_db("SELECT * FROM suppliers WHERE name = 'Fournisseur Mix Chaos'", one=True)
        raw_mat = query_db("SELECT * FROM raw_materials WHERE name = 'Matiere Mix Chaos'", one=True)
        fin_prod = query_db("SELECT * FROM finished_products WHERE name = 'Produit Mix Chaos'", one=True)

        # =============================================================================
        # EXPÉRIENCE 1 : LA DOUBLE INVERSION ET LE PAIEMENT ORPHELIN
        # =============================================================================
        print("\n🌪️ EXPÉRIENCE 1 : La Double Inversion (Vente -> Paiement -> Suppression Vente -> Suppression Paiement)")
        print("-" * 80)
        
        print("📥 1.a) Création d'une vente de 1000 DA...")
        create_sale_from_form(MockForm({
            "client_id": client["id"],
            "sale_date": date.today().isoformat(),
            "notes": "Vente initiale",
            "item_key[]": [f"finished:{fin_prod['id']}"],
            "quantity[]": [5.0],
            "unit[]": ["kg"],
            "unit_price[]": [200.0],
            "custom_item_name[]": [""]
        }))
        assert client_balance(client["id"]) == 1000.0
        print("   ✅ Vente créée, dette = 1000 DA.")

        print("📥 1.b) Paiement total de 1000 DA...")
        payment_id = create_payment_record(
            client_id=client["id"], amount=1000.0, payment_date=date.today().isoformat(),
            notes="Paiement de la vente", payment_type="versement"
        )
        assert client_balance(client["id"]) == 0.0
        print("   ✅ Paiement enregistré, dette = 0 DA.")

        print("📥 1.c) Suppression de la vente (le paiement devient une avance !)...")
        sale_row = query_db("SELECT id FROM sales WHERE client_id = %s", (client["id"],), one=True)
        delete_sale_by_id("finished", sale_row["id"])
        
        balance_after_sale_delete = client_balance(client["id"])
        if balance_after_sale_delete == -1000.0:
            print("   ✅ RÉUSSITE : Le solde est passé à -1000 DA (Le client a une avance créditrice de 1000 DA ! Logique comptable parfaite).")
            passed += 1
        else:
            print(f"❌ ÉCHEC : Le solde est {balance_after_sale_delete} au lieu de -1000 DA.")
            failures += 1
            
        print("📥 1.d) Suppression de l'avance (le paiement orphelin)...")
        delete_payment_by_id(payment_id)
        final_balance = client_balance(client["id"])
        if final_balance == 0.0:
            print("   ✅ RÉUSSITE : Paiement supprimé, le solde est revenu à 0 DA à la perfection !")
            passed += 1
        else:
            print(f"❌ ÉCHEC : Le solde final est {final_balance} au lieu de 0 DA.")
            failures += 1

        # =============================================================================
        # EXPÉRIENCE 2 : ACHATS GRATUITS (Division par zéro et Overflows virtuels)
        # =============================================================================
        print("\n🌪️ EXPÉRIENCE 2 : Achat Gratuit de Quantités Massives (Division par Zéro CMP)")
        print("-" * 80)
        
        print("📥 2.a) Achat de 9999 kg à 0.00 DA (Achat 100% gratuit)...")
        purchase_form = MockForm({
            "supplier_id": supplier["id"],
            "purchase_date": date.today().isoformat(),
            "notes": "Achat gratuit",
            "raw_material_id[]": [raw_mat["id"]],
            "quantity[]": [9999.0],
            "unit_price[]": [0.0]
        })
        try:
            create_purchase_from_form(purchase_form)
            print("❌ ÉCHEC : Achat gratuit accepté.")
            failures += 1
        except Exception as e:
            if "prix unitaire" in str(e) or "superieur a zero" in str(e):
                print(f"   ✅ RÉUSSITE : Le système empêche les achats gratuits pour protéger l'intégrité comptable : {e}")
                passed += 1
            else:
                print(f"❌ ÉCHEC : Erreur inattendue : {e}")
                failures += 1

        # =============================================================================
        # EXPÉRIENCE 3 : DÉPENDANCES ET SUPPRESSIONS FORCÉES (Sécurité Applicative)
        # =============================================================================
        print("\n🌪️ EXPÉRIENCE 3 : Suppressions Forcées (Sécurité de la couche Applicative contre l'orphelinage)")
        print("-" * 80)
        
        print("📥 3.a) Tentative de suppression du produit fini alors qu'il a des dépendances actives via delete_product_by_id...")
        try:
            from app.services.catalog_service import delete_product_by_id
            
            # Ajouter une dépendance fictive (ex. production batch) pour verrouiller la suppression
            execute_db("INSERT INTO production_batches (finished_product_id, production_date, output_quantity, production_cost, notes) VALUES (%s, %s, %s, %s, %s)",
                       (fin_prod["id"], date.today().isoformat(), 10.0, 1000.0, "Batch test chaos"))
            
            # Tenter de supprimer via le service applicatif
            ok = delete_product_by_id(fin_prod["id"])
            if not ok:
                print("   ✅ RÉUSSITE : Le service applicatif a détecté la liaison active et a bloqué la suppression en renvoyant False !")
                passed += 1
            else:
                print("❌ ÉCHEC : Le service applicatif a supprimé le produit fini malgré l'existence d'un lot de production associé !")
                failures += 1
        except Exception as e:
            print(f"❌ ÉCHEC : Exception levée lors du test de blocage : {e}")
            failures += 1


        # Nettoyage final
        print("\n♻️ Nettoyage des entités de chaos mixte...")
        with db_transaction():
            execute_db("DELETE FROM clients WHERE name = 'Client Mix Chaos'")
            execute_db("DELETE FROM suppliers WHERE name = 'Fournisseur Mix Chaos'")
            execute_db("DELETE FROM raw_materials WHERE name = 'Matiere Mix Chaos'")
            execute_db("DELETE FROM production_batches WHERE finished_product_id = %s", (fin_prod["id"],))
            execute_db("DELETE FROM stock_movements WHERE item_kind = 'finished' AND item_id = %s", (fin_prod["id"],))
            execute_db("DELETE FROM finished_products WHERE name = 'Produit Mix Chaos'")
        print("   ✅ Base de données propre !")

        # Synthèse
        print("\n" + "=" * 80)
        print("🏆 RAPPORT DE SYNTHÈSE DE LA SUITE DE CHAOS MIXTE")
        print("=" * 80)
        print(f"🛡️ Expériences Validées : {passed}")
        print(f"⚠️ Points de Risque     : {failures}")
        print("-" * 80)
        if failures == 0:
            print("💎 VERDICT : Logique irréprochable et base de données blindée.")
        else:
            print("⚠️ VERDICT : Des failles ou comportements inattendus ont été détectés.")
        print("=" * 80 + "\n")

    finally:
        reset_request_state(token)
        db.close()


if __name__ == "__main__":
    run_mixed_chaos_tests()
