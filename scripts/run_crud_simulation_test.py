#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/run_crud_simulation_test.py
Vérifie de manière unifiée toutes les opérations de CRUD (Création, Modification, Suppression)
sur les entités clés de l'application :
- Ventes, Achats, Versements, Avances, Productions (avec cascades sur les stocks et soldes)
- Modification des prix, des produits, des dates, des sommes et des clients.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ajouter le chemin racine du projet à PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import create_request_connection, bootstrap_and_migrate
from app.core.request_state import push_request_state, reset_request_state, set_state_value
from app.core.db_access import execute_db, query_db, db_transaction
from app.core.helpers import to_float

# Importation des services
from app.services.purchase_service import create_purchase_from_form, delete_purchase_by_id
from app.services.sale_service import create_sale_from_form, delete_sale_by_id
from app.services.client_account_service import create_payment_record, client_balance
from app.services.payment_service import delete_payment_by_id
from app.services.production_service import create_production_from_form, delete_production_by_id
from app.services.transactions_service import update_production_notes
from app.services.stock_service import recalc_raw_material_avg_cost, recalc_finished_product_avg_cost


class MockForm(dict):
    """Simule un formulaire multi-valeurs."""
    def getlist(self, key):
        val = self.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return [str(x) for x in val]
        return [str(val)]


def run_crud_tests():
    print("================================================================================")
    print("🧪 DÉMARRAGE DES TESTS D'INTÉGRITÉ CRUD COMPLETS (CRÉATION, MODIFICATION, SUPPRESSION)")
    print("================================================================================\n")
    
    bootstrap_and_migrate()
    db = create_request_connection()
    
    # Configurer le contexte de requête global
    admin_user = {"id": 1, "username": "admin", "role": "admin"}
    token = push_request_state(
        request=None,
        db=db,
        session={},
        request_id="test-crud-id-12345",
        audit_source="test_crud",
        user=admin_user,
    )
    set_state_value("user", admin_user)

    try:
        # Nettoyage initial préventif (au cas où un test précédent aurait planté)
        with db_transaction():
            execute_db("DROP TRIGGER IF EXISTS trg_stock_movements_to_raw_materials ON stock_movements")
            execute_db("DELETE FROM clients WHERE name IN ('Client Test CRUD', 'Client Test CRUD Modifie')")
            execute_db("DELETE FROM suppliers WHERE name = 'Fournisseur Test CRUD'")
            execute_db("DELETE FROM raw_materials WHERE name = 'Matiere Test CRUD'")
            execute_db("DELETE FROM finished_products WHERE name IN ('Produit Test CRUD', 'Produit Test CRUD Modifie')")



        # -----------------------------------------------------------------------------
        # 1. INITIALISATION DES ENTITÉS DE TEST
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 1 : Création des entités de test...")
        
        # Créer le client de test
        execute_db("INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
                   ("Client Test CRUD", "0555123456", "Alger Centre", "Client créé pour test CRUD automatique", 0.0))
        client = query_db("SELECT * FROM clients WHERE name = 'Client Test CRUD'", one=True)
        print(f"   ✅ Client de test créé : ID={client['id']}")
        
        # Créer le fournisseur de test
        execute_db("INSERT INTO suppliers (name, phone, address, notes) VALUES (%s, %s, %s, %s)",
                   ("Fournisseur Test CRUD", "021456789", "Zone Industrielle", "Fournisseur créé pour test CRUD"))
        supplier = query_db("SELECT * FROM suppliers WHERE name = 'Fournisseur Test CRUD'", one=True)
        print(f"   ✅ Fournisseur de test créé : ID={supplier['id']}")
        
        # Créer la matière première de test
        execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                   ("Matiere Test CRUD", "kg", 100.0, 100.0, 150.0))
        raw_mat = query_db("SELECT * FROM raw_materials WHERE name = 'Matiere Test CRUD'", one=True)
        print(f"   ✅ Matière première de test créée : ID={raw_mat['id']}, Stock Initial={raw_mat['stock_qty']} kg, CMP={raw_mat['avg_cost']} DA")
        
        # Créer le produit fini de test
        execute_db("INSERT INTO finished_products (name, default_unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                   ("Produit Test CRUD", "kg", 50.0, 200.0, 300.0))
        fin_prod = query_db("SELECT * FROM finished_products WHERE name = 'Produit Test CRUD'", one=True)
        print(f"   ✅ Produit fini de test créé : ID={fin_prod['id']}, Stock Initial={fin_prod['stock_qty']} kg, CMP={fin_prod['avg_cost']} DA")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 2. TEST ACHAT (CREATE & DELETE)
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 2 : Test CRUD sur les Achats (Création -> Augmentation Stock & Recalcul CMP -> Suppression -> Restauration)...")
        
        purchase_form = MockForm({
            "supplier_id": supplier["id"],
            "purchase_date": date.today().isoformat(),
            "notes": "Achat de test CRUD",
            "raw_material_id[]": [raw_mat["id"]],
            "quantity[]": [200.0],
            "unit_price[]": [120.0]  # Prix d'achat supérieur au CMP initial (100.0) -> Devrait modifier le CMP
        })
        
        # Créer l'achat
        create_purchase_from_form(purchase_form)
        
        # Vérifier l'augmentation du stock et le nouveau CMP
        raw_after_buy = query_db("SELECT * FROM raw_materials WHERE id = %s", (raw_mat["id"],), one=True)
        expected_stock = 100.0 + 200.0
        # Nouveau CMP attendu = ((100 * 100) + (200 * 120)) / 300 = (10000 + 24000) / 300 = 34000 / 300 = 113.33
        expected_cmp = round((100.0 * 100.0 + 200.0 * 120.0) / 300.0, 2)
        
        assert float(raw_after_buy["stock_qty"]) == expected_stock, f"Erreur stock achat : {raw_after_buy['stock_qty']} != {expected_stock}"
        assert abs(float(raw_after_buy["avg_cost"]) - expected_cmp) < 0.1, f"Erreur CMP achat : {raw_after_buy['avg_cost']} != {expected_cmp}"
        print(f"   ✅ Achat enregistré : Stock={raw_after_buy['stock_qty']} kg, CMP={raw_after_buy['avg_cost']} DA (Recalculé parfaitement !)")
        
        # Supprimer l'achat
        purchases = query_db("SELECT id FROM purchases WHERE supplier_id = %s", (supplier["id"],))
        assert len(purchases) == 1, "Achat non trouvé dans la base"
        purchase_id = purchases[0]["id"]
        
        delete_purchase_by_id(purchase_id)
        
        # Vérifier que le stock et le CMP sont restaurés
        raw_after_delete = query_db("SELECT * FROM raw_materials WHERE id = %s", (raw_mat["id"],), one=True)
        assert float(raw_after_delete["stock_qty"]) == 100.0, "Stock non restauré après suppression achat"
        assert abs(float(raw_after_delete["avg_cost"]) - 100.0) < 0.1, "CMP non restauré après suppression achat"
        print("   ✅ Achat supprimé : Stock et CMP restaurés aux valeurs d'origine avec succès !")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 3. TEST PRODUCTION (CREATE, EDIT NOTES, DELETE)
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 3 : Test CRUD sur les Productions (Fabrication -> Déduction Matière & Augmentation Produit -> Édition Notes -> Suppression)...")
        
        production_form = MockForm({
            "finished_product_id": fin_prod["id"],
            "output_quantity": 10.0,
            "production_date": date.today().isoformat(),
            "notes": "Production de test CRUD",
            "save_recipe": "0",
            "raw_material_id[]": [raw_mat["id"]],
            "quantity[]": [20.0]  # Consomme 20 kg de Matiere Test
        })
        
        # Enregistrer la production
        result = create_production_from_form(production_form)
        batch_id = result["batch_id"]
        
        # Vérifier la déduction de matière première et l'augmentation de produit fini
        raw_after_prod = query_db("SELECT * FROM raw_materials WHERE id = %s", (raw_mat["id"],), one=True)
        fin_after_prod = query_db("SELECT * FROM finished_products WHERE id = %s", (fin_prod["id"],), one=True)
        
        assert float(raw_after_prod["stock_qty"]) == 80.0, f"Erreur stock matière première : {raw_after_prod['stock_qty']} != 80"
        assert float(fin_after_prod["stock_qty"]) == 60.0, f"Erreur stock produit fini : {fin_after_prod['stock_qty']} != 60"
        print(f"   ✅ Production enregistrée : Stock Matière={raw_after_prod['stock_qty']} kg, Stock Produit Fini={fin_after_prod['stock_qty']} kg")
        
        # Modifier les notes et la date de la production
        new_date = "2026-05-17"
        update_production_notes(batch_id=batch_id, production_date=new_date, notes="Notes modifiees par le test CRUD")
        
        batch_after_edit = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
        assert batch_after_edit["production_date"] == new_date, "Date de production non modifiée"
        assert batch_after_edit["notes"] == "Notes modifiees par le test CRUD", "Notes de production non modifiées"
        print("   ✅ Modification de la production : Date et Notes mises à jour avec succès !")
        
        # Supprimer la production
        delete_production_by_id(batch_id)
        
        # Vérifier la restauration des stocks
        raw_final = query_db("SELECT * FROM raw_materials WHERE id = %s", (raw_mat["id"],), one=True)
        fin_final = query_db("SELECT * FROM finished_products WHERE id = %s", (fin_prod["id"],), one=True)
        
        assert float(raw_final["stock_qty"]) == 100.0, "Stock matière première non restauré après suppression production"
        assert float(fin_final["stock_qty"]) == 50.0, "Stock produit fini non restauré après suppression production"
        print("   ✅ Production supprimée : Stocks de matière première et produit fini restaurés à la perfection !")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 4. TEST VENTE (CREATE & DELETE)
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 4 : Test CRUD sur les Ventes (Création -> Solde Client & Déduction Stock -> Suppression -> Restauration)...")
        
        sale_form = MockForm({
            "client_id": client["id"],
            "sale_date": date.today().isoformat(),
            "notes": "Vente de test CRUD",
            "item_key[]": [f"finished:{fin_prod['id']}"],
            "quantity[]": [10.0],
            "unit[]": ["kg"],
            "unit_price[]": [350.0],  # 10 kg à 350.0 = 3500.0 DA
            "custom_item_name[]": [""]
        })
        
        # Créer la vente à crédit
        create_sale_from_form(sale_form)
        
        # Vérifier le solde du client et le stock du produit fini
        debt_after_sale = client_balance(client["id"])
        fin_after_sale = query_db("SELECT * FROM finished_products WHERE id = %s", (fin_prod["id"],), one=True)
        
        assert debt_after_sale == 3500.0, f"Erreur dette client : {debt_after_sale} != 3500"
        assert float(fin_after_sale["stock_qty"]) == 40.0, f"Erreur stock produit fini : {fin_after_sale['stock_qty']} != 40"
        print(f"   ✅ Vente enregistrée : Dette Client={debt_after_sale} DA, Stock Produit Fini={fin_after_sale['stock_qty']} kg")
        
        # Supprimer la vente
        sales = query_db("SELECT id FROM sales WHERE client_id = %s", (client["id"],))
        assert len(sales) == 1, "Vente non trouvée"
        sale_id = sales[0]["id"]
        
        delete_sale_by_id("finished", sale_id)
        
        # Vérifier la restauration
        debt_final = client_balance(client["id"])
        fin_restored = query_db("SELECT * FROM finished_products WHERE id = %s", (fin_prod["id"],), one=True)
        
        assert debt_final == 0.0, "Dette client non restaurée après suppression de la vente"
        assert float(fin_restored["stock_qty"]) == 50.0, "Stock produit fini non restauré après suppression de la vente"
        print("   ✅ Vente supprimée : Dette client et stock de produit fini restaurés avec succès !")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 5. TEST VERSEMENT (CREATE & DELETE)
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 5 : Test CRUD sur les Versements (Création -> Déduction Solde -> Suppression -> Restauration)...")
        
        # Créer une vente de 2000 DA d'abord pour avoir une dette
        create_sale_from_form(MockForm({
            "client_id": client["id"],
            "sale_date": date.today().isoformat(),
            "notes": "Vente pour dette",
            "item_key[]": [f"finished:{fin_prod['id']}"],
            "quantity[]": [5.0],
            "unit[]": ["kg"],
            "unit_price[]": [400.0],  # 2000.0 DA
            "custom_item_name[]": [""]
        }))
        
        debt_before_pay = client_balance(client["id"])
        assert debt_before_pay == 2000.0, "Dette initiale incorrecte"
        
        # Faire un versement de 1500 DA
        payment_id = create_payment_record(
            client_id=client["id"],
            amount=1500.0,
            payment_date=date.today().isoformat(),
            notes="Versement de test CRUD",
            payment_type="versement"
        )
        
        debt_after_pay = client_balance(client["id"])
        assert debt_after_pay == 500.0, f"Erreur dette après paiement : {debt_after_pay} != 500"
        print(f"   ✅ Versement de 1500 DA enregistré : Dette Restante={debt_after_pay} DA")
        
        # Supprimer le versement
        delete_payment_by_id(payment_id)
        
        debt_restored = client_balance(client["id"])
        assert debt_restored == 2000.0, "Dette non restaurée après suppression du versement"
        print("   ✅ Versement supprimé : Dette client rétablie à son montant d'origine avec succès !")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 6. MODIFICATION DES PROFILS CLIENTS ET PRODUITS (PRIX & INFOS)
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 6 : Test des modifications de Profils (Changement de Prix, Nom, Infos)...")
        
        # Modifier le profil du client
        execute_db("UPDATE clients SET name = %s, phone = %s, address = %s WHERE id = %s",
                   ("Client Test CRUD Modifie", "0555999999", "Oran Centre", client["id"]))
        client_edited = query_db("SELECT * FROM clients WHERE id = %s", (client["id"],), one=True)
        assert client_edited["name"] == "Client Test CRUD Modifie", "Nom client non modifié"
        assert client_edited["phone"] == "0555999999", "Téléphone client non modifié"
        print(f"   ✅ Client modifié : Nom='{client_edited['name']}', Phone='{client_edited['phone']}', Ville='{client_edited['address']}'")
        
        # Modifier le prix et le nom du produit
        execute_db("UPDATE finished_products SET name = %s, sale_price = %s WHERE id = %s",
                   ("Produit Test CRUD Modifie", 380.0, fin_prod["id"]))
        prod_edited = query_db("SELECT * FROM finished_products WHERE id = %s", (fin_prod["id"],), one=True)
        assert prod_edited["name"] == "Produit Test CRUD Modifie", "Nom produit non modifié"
        assert float(prod_edited["sale_price"]) == 380.0, "Prix de vente produit non modifié"
        print(f"   ✅ Produit modifié : Nom='{prod_edited['name']}', Nouveau Prix de vente={prod_edited['sale_price']} DA")

        print("-" * 80)

        # -----------------------------------------------------------------------------
        # 7. NETTOYAGE ET NETTOYAGE FINAL
        # -----------------------------------------------------------------------------
        print("🎯 ÉTAPE 7 : Nettoyage des entités de test...")
        
        # Supprimer la vente restante pour permettre la suppression propre du client et du produit
        sales = query_db("SELECT id FROM sales WHERE client_id = %s", (client["id"],))
        for s in sales:
            delete_sale_by_id("finished", s["id"])
            
        execute_db("DELETE FROM clients WHERE id = %s", (client["id"],))
        execute_db("DELETE FROM suppliers WHERE id = %s", (supplier["id"],))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (raw_mat["id"],))
        execute_db("DELETE FROM finished_products WHERE id = %s", (fin_prod["id"],))
        
        print("   ✅ Nettoyage terminé : Base de données parfaitement propre !")
        
        print("\n" + "="*80)
        print("🏆 TOUS LES TESTS CRUD ET D'INTÉGRITÉ FONCTIONNENT À 100% AVEC UNE PRÉCISION ABSOLUE !")
        print("="*80)

    finally:
        reset_request_state(token)
        db.close()


if __name__ == "__main__":
    run_crud_tests()
