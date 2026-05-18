#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/production_simulation.py
Simule 500 opérations réelles (achats, ventes, versements, avances, productions)
de manière logique et aléatoire avec les entités de l'application.
"""

from __future__ import annotations

import os
import sys
import random
from datetime import date, timedelta
from pathlib import Path

# Ajouter le chemin racine du projet à PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings
from app.core.database import create_request_connection, bootstrap_and_migrate
from app.core.request_state import push_request_state, reset_request_state, set_state_value
from app.core.db_access import execute_db, query_db, db_transaction
from app.core.helpers import to_float

# Importation des services
from app.services.purchase_service import create_purchase_from_form
from app.services.sale_service import create_sale_from_form
from app.services.client_account_service import create_payment_record, client_balance
from app.services.production_service import create_production_from_form
from app.services.stock_service import recalc_raw_material_avg_cost, recalc_finished_product_avg_cost


class MockForm(dict):
    """Simule un dictionnaire de formulaire multi-valeurs de Starlette."""
    def getlist(self, key):
        val = self.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return [str(x) for x in val]
        return [str(val)]


def setup_simulation_data(db):
    """S'assure que nous avons des entités cohérentes pour la simulation."""
    print("📥 Initialisation et vérification des données de simulation...")
    
    # 1. Utilisateurs
    admin = query_db("SELECT id FROM users WHERE username = 'admin'", one=True)
    if not admin:
        execute_db(
            "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, %s, %s)",
            ("admin", "pbkdf2:sha256:260000$mock_hash_0000", "admin", True)
        )
        print("👤 Utilisateur 'admin' créé.")
    
    # 2. Clients
    clients = query_db("SELECT id, name FROM clients")
    if len(clients) < 5:
        names = ["Client Simulation Alpha", "Client Simulation Beta", "Client Simulation Gamma", "Client Simulation Delta", "Client Simulation Epsilon"]
        for name in names:
            if not any(c["name"] == name for c in clients):
                execute_db("INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
                           (name, "0555000000", "Alger", "Client de test simulation", 0.0))
        clients = query_db("SELECT id, name FROM clients")
        print(f"👥 Clients assurés : {len(clients)} clients disponibles.")
        
    # 3. Fournisseurs
    suppliers = query_db("SELECT id, name FROM suppliers")
    if len(suppliers) < 2:
        names = ["Fournisseur Direct Chimie", "Fournisseur Plastique Algérie"]
        for name in names:
            if not any(s["name"] == name for s in suppliers):
                execute_db("INSERT INTO suppliers (name, phone, address, notes) VALUES (%s, %s, %s, %s)",
                           (name, "021000000", "Oran", "Fournisseur de test simulation"))
        suppliers = query_db("SELECT id, name FROM suppliers")
        print(f"🏭 Fournisseurs assurés : {len(suppliers)} fournisseurs disponibles.")

    # 4. Matières Premières
    raws = query_db("SELECT id, name FROM raw_materials")
    if len(raws) < 3:
        materials = [
            ("Granulés Plastiques", "kg", 1000.0, 120.0, 150.0),
            ("Colorant Noir", "kg", 500.0, 350.0, 450.0),
            ("Additif Stabilisant", "kg", 200.0, 200.0, 280.0)
        ]
        for name, unit, qty, cost, price in materials:
            if not any(r["name"] == name for r in raws):
                execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                           (name, unit, qty, cost, price))
        raws = query_db("SELECT id, name FROM raw_materials")
        print(f"📦 Matières premières assurées : {len(raws)} articles disponibles.")

    # 5. Produits Finis
    products = query_db("SELECT id, name FROM finished_products")
    if len(products) < 2:
        items = [
            ("Caisse Plastique 15L", "kg", 500.0, 180.0, 250.0),
            ("Palette Plastique HD", "kg", 250.0, 300.0, 420.0)
        ]
        for name, unit, qty, cost, price in items:
            if not any(p["name"] == name for p in products):
                execute_db("INSERT INTO finished_products (name, unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)",
                           (name, unit, qty, cost, price))
        products = query_db("SELECT id, name FROM finished_products")
        print(f"🏭 Produits finis assurés : {len(products)} articles disponibles.")

    return {
        "clients": query_db("SELECT id, name FROM clients"),
        "suppliers": query_db("SELECT id, name FROM suppliers"),
        "raw_materials": query_db("SELECT id, name, stock_qty, avg_cost, sale_price FROM raw_materials"),
        "finished_products": query_db("SELECT id, name, stock_qty, avg_cost, sale_price FROM finished_products")
    }


def run_simulation(operations_count=500):
    bootstrap_and_migrate()
    db = create_request_connection()
    
    # Configurer le contexte de requête global
    admin_user = {"id": 1, "username": "admin", "role": "admin"}
    token = push_request_state(
        request=None,
        db=db,
        session={},
        request_id="simulation-id-12345",
        audit_source="simulation",
        user=admin_user,
    )
    set_state_value("user", admin_user)

    try:
        data = setup_simulation_data(db)
        
        print("\n🚀 Démarrage de la simulation industrielle en cascade (100 Achats -> 50 Productions -> 500 Ventes)...")
        
        counts = {"achat": 0, "vente": 0, "versement": 0, "avance": 0, "production": 0}
        total_financial_volume = 0.0
        
        # --- ÉTAPE 1 : 100 ACHATS D'APPROVISIONNEMENT ---
        print("\n🛒 --- ÉTAPE 1 : 100 ACHATS DE MATIÈRES PREMIÈRES ---")
        for i in range(1, 101):
            op_date = (date.today() - timedelta(days=random.randint(15, 30))).isoformat()
            supplier = random.choice(data["suppliers"])
            material = random.choice(data["raw_materials"])
            qty = round(random.uniform(100.0, 500.0), 2)
            price = round(float(material["avg_cost"]) * random.uniform(0.9, 1.1), 2)
            total = qty * price
            
            form = MockForm({
                "supplier_id": supplier["id"],
                "purchase_date": op_date,
                "notes": f"Achat approvisionnement #{i}",
                "raw_material_id[]": [material["id"]],
                "quantity[]": [qty],
                "unit_price[]": [price]
            })
            
            try:
                create_purchase_from_form(form)
                counts["achat"] += 1
                total_financial_volume += total
                print(f"🛒 #{i:03d} | ACHAT      | {qty:6.1f} kg de '{material['name']}' chez '{supplier['name']}' pour {total:8.2f} DA")
            except Exception as e:
                print(f"⚠️ Achat #{i} échoué : {e}")

        # Re-charger l'état des matières après achats
        data["raw_materials"] = query_db("SELECT id, name, stock_qty, avg_cost, sale_price FROM raw_materials")

        # --- ÉTAPE 2 : 50 PRODUCTIONS AVEC RECETTES PRÉCISES ---
        print("\n⚙️ --- ÉTAPE 2 : 50 PRODUCTIONS INDUSTRIELLES ---")
        for i in range(1, 51):
            op_date = (date.today() - timedelta(days=random.randint(5, 15))).isoformat()
            product = random.choice(data["finished_products"])
            output_qty = round(random.uniform(50.0, 150.0), 2)
            
            # Recette standard : Consomme 70% de la matière première 1 et 30% de la matière première 2
            raw_materials_list = list(data["raw_materials"])
            if len(raw_materials_list) >= 2:
                r1, r2 = raw_materials_list[0], raw_materials_list[1]
                qty1 = round(output_qty * 0.7, 2)
                qty2 = round(output_qty * 0.3, 2)
                raw_ids = [r1["id"], r2["id"]]
                quantities = [qty1, qty2]
            else:
                r1 = raw_materials_list[0]
                qty1 = round(output_qty * 1.0, 2)
                raw_ids = [r1["id"]]
                quantities = [qty1]

            # S'assurer du stock de matières premières avant de produire
            for rid, rqty in zip(raw_ids, quantities):
                execute_db("UPDATE raw_materials SET stock_qty = stock_qty + %s WHERE id = %s", (rqty * 1.5, rid))
            
            form = MockForm({
                "finished_product_id": product["id"],
                "output_quantity": output_qty,
                "production_date": op_date,
                "notes": f"Production lot #{i} (Recette standard)",
                "save_recipe": "0",
                "raw_material_id[]": raw_ids,
                "quantity[]": quantities
            })
            
            try:
                create_production_from_form(form)
                counts["production"] += 1
                print(f"⚙️  #{i:03d} | PRODUCTION | {output_qty:6.1f} kg de '{product['name']}' fabriqués")
            except Exception as e:
                print(f"⚠️ Production #{i} échouée : {e}")

        # Re-charger l'état de tous les articles après production
        data["raw_materials"] = query_db("SELECT id, name, stock_qty, avg_cost, sale_price FROM raw_materials")
        data["finished_products"] = query_db("SELECT id, name, stock_qty, avg_cost, sale_price FROM finished_products")

        # --- ÉTAPE 3 : 500 VENTES ET ACTIONS CLIENTS ---
        print("\n💰 --- ÉTAPE 3 : 500 VENTES ET ENCAISSEMENTS ---")
        for i in range(1, 501):
            op_date = (date.today() - timedelta(days=random.randint(0, 5))).isoformat()
            
            # 85% de chances de faire une vente, 10% de versement, 5% d'avance
            action_choice = random.choices(["vente", "versement", "avance"], weights=[85, 10, 5], k=1)[0]
            
            if action_choice == "vente":
                client = random.choice(data["clients"])
                kind = random.choice(["finished", "raw"])
                
                if kind == "finished":
                    item = random.choice(data["finished_products"])
                    item_key = f"finished:{item['id']}"
                else:
                    item = random.choice(data["raw_materials"])
                    item_key = f"raw:{item['id']}"
                
                qty = round(random.uniform(5.0, 80.0), 2)
                
                # Assurer le stock de l'article pour ne pas faire échouer la vente
                execute_db(f"UPDATE {'finished_products' if kind == 'finished' else 'raw_materials'} SET stock_qty = stock_qty + %s WHERE id = %s", (qty * 1.5, item["id"]))
                
                price = round(float(item["sale_price"]) * random.uniform(0.95, 1.05), 2)
                total = qty * price
                
                form = MockForm({
                    "client_id": client["id"],
                    "sale_date": op_date,
                    "notes": f"Vente lot simulation #{i}",
                    "item_key[]": [item_key],
                    "quantity[]": [qty],
                    "unit[]": ["kg"],
                    "unit_price[]": [price],
                    "custom_item_name[]": [""]
                })
                
                try:
                    create_sale_from_form(form)
                    counts["vente"] += 1
                    total_financial_volume += total
                    print(f"💰 #{i:03d} | VENTE      | {qty:6.1f} kg de '{item['name']}' à '{client['name']}' pour {total:8.2f} DA")
                except Exception as e:
                    print(f"⚠️ Vente #{i} échouée : {e}")

            elif action_choice == "versement":
                client = random.choice(data["clients"])
                debt = client_balance(client["id"])
                if debt > 0:
                    amount = round(random.uniform(1000.0, min(30000.0, debt)), 2)
                    try:
                        create_payment_record(
                            client_id=client["id"],
                            amount=amount,
                            payment_date=op_date,
                            notes=f"Versement simulation #{i}",
                            payment_type="versement"
                        )
                        counts["versement"] += 1
                        total_financial_volume += amount
                        print(f"💳 #{i:03d} | VERSEMENT  | '{client['name']}' a versé {amount:8.2f} DA (Dette restante: {debt - amount:.2f} DA)")
                    except Exception as e:
                        print(f"⚠️ Versement #{i} échoué : {e}")

            elif action_choice == "avance":
                client = random.choice(data["clients"])
                amount = round(random.uniform(2000.0, 20000.0), 2)
                try:
                    create_payment_record(
                        client_id=client["id"],
                        amount=amount,
                        payment_date=op_date,
                        notes=f"Avance simulation #{i}",
                        payment_type="avance"
                    )
                    counts["avance"] += 1
                    total_financial_volume += amount
                    print(f"💵 #{i:03d} | AVANCE     | '{client['name']}' a fait une avance de {amount:8.2f} DA")
                except Exception as e:
                    print(f"⚠️ Avance #{i} échouée : {e}")

        # --- BILAN FINAL DE LA SIMULATION ---
        print("\n" + "="*80)
        print("🏆 BILAN DE LA SIMULATION EN CASCADE (100 ACHATS -> 50 PRODUCTIONS -> 500 VENTES)")
        print("="*80)
        print(f"🛒 Nombre d'achats simulés       : {counts['achat']}")
        print(f"⚙️  Nombre de productions simulées : {counts['production']}")
        print(f"💰 Nombre de ventes simulées      : {counts['vente']}")
        print(f"💳 Nombre de versements simulés  : {counts['versement']}")
        print(f"💵 Nombre d'avances simulées     : {counts['avance']}")
        print("-"*80)
        print(f"📈 Volume financier total brassé  : {total_financial_volume:,.2f} DA")
        print("="*80)
        print("👥 ÉTAT FINANCIER ACTUEL DES CLIENTS SIMULÉS :")
        for c in data["clients"]:
            bal = client_balance(c["id"])
            status = "Débiteur" if bal > 0 else "Créditeur (Avance)" if bal < 0 else "Soldé"
            print(f"   • {c['name']:<28} : {abs(bal):10.2f} DA ({status})")
        print("="*80)

    finally:
        db.close()
        reset_request_state(token)


if __name__ == "__main__":
    run_simulation(500)
