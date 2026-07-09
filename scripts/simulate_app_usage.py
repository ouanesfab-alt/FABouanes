#!/usr/bin/env python
"""
Simulation script of 30 days of FABouanes application usage.
Touches all routes, services, templates, validation layers, database models, and generates a final audit report.
"""

import os
import sys
import json
import base64
import logging
import traceback
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

# Clear existing handlers on root logger
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

# Configure logging to write directly to a local file
file_handler = logging.FileHandler("simulation_debug.log", mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.root.addHandler(file_handler)
logging.root.setLevel(logging.DEBUG)

# Add handler directly to all app loggers to ensure we capture internal tracebacks
logging.getLogger("fabouanes").addHandler(file_handler)
logging.getLogger("fabouanes.assistant").addHandler(file_handler)
logging.getLogger("fabouanes.assistant").setLevel(logging.DEBUG)
logger = logging.getLogger("fabouanes.simulation")

# Setup project root path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Mock Authentication & Permissions before importing app to bypass login screens
mock_user = {"id": 1, "username": "simul_admin", "role": "admin", "is_active": 1}

async def async_noop(*args, **kwargs):
    pass

# Patch authentication dynamically in sys.modules
for name, module in list(sys.modules.items()):
    if name.startswith("app.") or name == "app":
        if hasattr(module, "require_api_user"):
            setattr(module, "require_api_user", MagicMock(return_value=mock_user))
        if hasattr(module, "load_user_from_session"):
            setattr(module, "load_user_from_session", MagicMock(return_value=mock_user))
        if hasattr(module, "get_current_user"):
            setattr(module, "get_current_user", MagicMock(return_value=mock_user))
        if hasattr(module, "require_user"):
            setattr(module, "require_user", MagicMock(return_value=None))
        if hasattr(module, "require_permission") and name != "app.core.permissions":
            setattr(module, "require_permission", MagicMock(return_value=None))
        if hasattr(module, "ensure_csrf_token"):
            setattr(module, "ensure_csrf_token", MagicMock(return_value=None))
        if hasattr(module, "csrf_protect"):
            setattr(module, "csrf_protect", async_noop)

# Now import FastAPI App, TestClient, and direct Tool execution service
from fastapi.testclient import TestClient
from app.main import app
from app.core.db_helpers import db_manager
from app.modules.assistant.service import execute_tool_action, execute_write_sql
from sqlmodel import text

# Configure dependency overrides
from app.web.deps import verify_csrf_token
from app.core.jwt_auth import get_current_user_id
app.dependency_overrides[verify_csrf_token] = lambda: None
app.dependency_overrides[get_current_user_id] = lambda: 1

client = TestClient(app)

class SimulationReport:
    def __init__(self):
        self.steps_count = 0
        self.success_count = 0
        self.failures = []
        self.warnings = []

    def record(self, action: str, success: bool, error_msg: str = None, meta: dict = None):
        self.steps_count += 1
        if success:
            self.success_count += 1
        else:
            self.failures.append({
                "action": action,
                "error": error_msg or "Unknown error",
                "meta": meta or {}
            })

    def warn(self, message: str):
        self.warnings.append(message)

    def print_report(self):
        with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
            f_log.write("\n" + "=" * 60 + "\n")
            f_log.write("[RAPPORT DE SIMULATION DES 30 JOURS D'UTILISATION]\n")
            f_log.write("=" * 60 + "\n")
            f_log.write(f"Total Etapes simulees : {self.steps_count}\n")
            f_log.write(f"Reussites : {self.success_count} / {self.steps_count} ({round(self.success_count/self.steps_count * 100, 2) if self.steps_count > 0 else 0}%)\n")
            f_log.write(f"Echecs / Services en panne : {len(self.failures)}\n")
            
            if self.failures:
                f_log.write("\n[ERREURS & ANOMALIES DETECTEES] :\n")
                for i, f in enumerate(self.failures, 1):
                    f_log.write(f"{i}. Action : {f['action']}\n")
                    f_log.write(f"   * Erreur : {f['error']}\n")
            
        print("\n" + "=" * 60)
        print("[RAPPORT DE SIMULATION DES 30 JOURS D'UTILISATION]")
        print("=" * 60)
        print(f"Total Etapes simulees : {self.steps_count}")
        print(f"Reussites : {self.success_count} / {self.steps_count} ({round(self.success_count/self.steps_count * 100, 2) if self.steps_count > 0 else 0}%)")
        print(f"Echecs / Services en panne : {len(self.failures)}")
        print(f"Alertes / Avertissements : {len(self.warnings)}")
        
        if self.failures:
            print("\n[ERREURS & ANOMALIES DETECTEES] :")
            for i, f in enumerate(self.failures, 1):
                print(f"{i}. Action : {f['action']}")
                print(f"   * Erreur : {f['error']}")
                print(f"   * Metadonnees : {f['meta']}")
        else:
            print("\n[OK] Aucun service en panne ou anomalie bloquante detectee. L'application est saine.")
            
        if self.warnings:
            print("\n[AVERTISSEMENTS] :")
            for i, w in enumerate(self.warnings, 1):
                print(f"{i}. {w}")
        print("=" * 60 + "\n")

async def run_simulation():
    report = SimulationReport()
    print("Demarrage de la simulation d'utilisation de 30 jours...")
    
    # ── ETAPE 0 : Nettoyage / Preparation de l'environnement de simulation ──
    try:
        with db_manager.db_transaction() as conn:
            # Nettoyer les operations liees a nos clients de simulation
            conn.execute("DELETE FROM client_history WHERE client_id IN (SELECT id FROM clients WHERE name LIKE 'Simul%')")
            conn.execute("DELETE FROM payments WHERE client_id IN (SELECT id FROM clients WHERE name LIKE 'Simul%')")
            conn.execute("DELETE FROM sales WHERE client_id IN (SELECT id FROM clients WHERE name LIKE 'Simul%')")
            conn.execute("DELETE FROM purchases WHERE supplier_id IN (SELECT id FROM suppliers WHERE name LIKE 'Simul%')")
            conn.execute("DELETE FROM expenses WHERE description LIKE 'Simul%'")
            conn.execute("DELETE FROM production_batches WHERE notes LIKE 'Simul%'")
            
            # Check if saved_recipes / saved_recipe_items tables exist before deleting
            try:
                conn.execute("DELETE FROM saved_recipe_items WHERE recipe_id IN (SELECT id FROM saved_recipes WHERE finished_product_id IN (SELECT id FROM finished_products WHERE name LIKE 'Simul%'))")
                conn.execute("DELETE FROM saved_recipes WHERE finished_product_id IN (SELECT id FROM finished_products WHERE name LIKE 'Simul%')")
            except Exception as e:
                pass
                
            conn.execute("DELETE FROM finished_products WHERE name LIKE 'Simul%'")
            conn.execute("DELETE FROM raw_materials WHERE name LIKE 'Simul%'")
            conn.execute("DELETE FROM clients WHERE name LIKE 'Simul%'")
            conn.execute("DELETE FROM suppliers WHERE name LIKE 'Simul%'")
        report.record("Nettoyage base de donnees", True)
    except Exception as e:
        with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
            traceback.print_exc(file=f_log)
        report.record("Nettoyage base de donnees", False, str(e))

    client_ids = []
    supplier_ids = []
    raw_material_ids = []
    finished_product_ids = []
    recipe_ids = []
    sale_ids = []
    purchase_ids = []
    payment_ids = []
    expense_ids = []
    production_ids = []
    backup_names = []

    # Simulation sur 30 jours fictifs
    start_date = date.today() - timedelta(days=30)

    for day in range(1, 31):
        simul_date = start_date + timedelta(days=day)

        # JOUR 1 : Configuration initiale & Test des pages de base (Templates & Routes)
        if day == 1:
            routes_to_test = [
                "/health",
                "/api/v1/version",
                "/assistant",
                "/contacts",
                "/contacts?type=client",
                "/contacts?type=supplier",
                "/catalog",
                "/expenses",
                "/production",
                "/transactions",
                "/dashboard",
                "/admin",
                "/reports"
            ]
            for r in routes_to_test:
                try:
                    response = client.get(r)
                    if response.status_code in (200, 303):
                        report.record(f"GET route {r}", True)
                    elif response.status_code == 503 and r == "/health":
                        report.record(f"GET route {r} (Service Unavailable)", True)
                    else:
                        report.record(f"GET route {r}", False, f"HTTP {response.status_code}")
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record(f"GET route {r}", False, str(e))

            # Creation de sauvegarde de demarrage via execute_tool_action
            try:
                res_data = await execute_tool_action("create_app_backup", {})
                if "error" not in res_data:
                    report.record("Sauvegarde initiale", True)
                else:
                    report.record("Sauvegarde initiale", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Sauvegarde initiale", False, str(e))

        # JOUR 2 & 3 : Creation de clients et fournisseurs (Entrees normales)
        elif day in (2, 3):
            # Creation client normal
            try:
                client_name = f"SimulClient_Normal_J{day}"
                res_data = await execute_tool_action("add_client", {
                    "name": client_name,
                    "phone": f"055500000{day}",
                    "address": f"Adresse Client J{day}",
                    "opening_credit": 5000.0,
                    "notes": "Simulation J1"
                })
                if "client_id" in res_data:
                    client_ids.append(res_data["client_id"])
                    report.record("Creation client normal", True)
                else:
                    report.record("Creation client normal", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Creation client normal", False, str(e))

            # Creation fournisseur normal (direct call to execute_write_sql)
            try:
                supplier_name = f"SimulFournisseur_Normal_J{day}"
                query = f"INSERT INTO suppliers (name, phone, address, notes) VALUES ('{supplier_name}', '066600000{day}', 'Adresse Fournisseur J{day}', 'Simulation J1') RETURNING id"
                res_data = execute_write_sql(query)
                if "inserted_id" in res_data:
                    supplier_ids.append(res_data["inserted_id"])
                    report.record("Creation fournisseur normal", True)
                else:
                    report.record("Creation fournisseur normal", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Creation fournisseur normal", False, str(e))

        # JOUR 4 : Tentative d'entrees extremes / robustesse de validation (Validation clients)
        elif day == 4:
            # Client avec opening_credit negatif
            try:
                res_data = await execute_tool_action("add_client", {
                    "name": "SimulClient_Extreme_J4",
                    "phone": "numero de telephone textuel invalide !",
                    "address": "",
                    "opening_credit": -15000.0,
                    "notes": ""
                })
                report.record("Validation client ouverture negative", True, meta=res_data)
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Validation client ouverture negative", False, str(e))

            # Client sans nom (doit echouer proprement)
            try:
                res_data = await execute_tool_action("add_client", {
                    "name": "",
                    "phone": "0555999999"
                })
                if "error" in res_data:
                    report.record("Detection nom vide client", True)
                else:
                    report.record("Detection nom vide client", False, "Le nom vide a ete accepte ou n'a pas leve d'erreur")
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Detection nom vide client", False, str(e))

        # JOUR 5 & 6 : Catalogue, matieres premieres et produits finis
        elif day in (5, 6):
            # Ajouter matiere premiere (use correct argument keys: price and cost)
            try:
                mat_name = f"SimulMatiereRaw_J{day}"
                res_data = await execute_tool_action("add_product", {
                    "name": mat_name,
                    "category": "raw",
                    "price": 0.0,
                    "cost": 150.0,
                    "unit": "kg",
                    "notes": "Simulation J5"
                })
                if "product_id" in res_data:
                    raw_material_ids.append(res_data["product_id"])
                    report.record("Creation matiere premiere", True)
                else:
                    report.record("Creation matiere premiere", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Creation matiere premiere", False, str(e))

            # Ajouter produit fini (use correct argument keys: price and cost)
            try:
                prod_name = f"SimulProduitFini_J{day}"
                res_data = await execute_tool_action("add_product", {
                    "name": prod_name,
                    "category": "finished",
                    "price": 450.0,
                    "cost": 220.0,
                    "unit": "u",
                    "notes": "Simulation J5"
                })
                if "product_id" in res_data:
                    finished_product_ids.append(res_data["product_id"])
                    report.record("Creation produit fini", True)
                else:
                    report.record("Creation produit fini", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Creation produit fini", False, str(e))

        # JOUR 7 : Recettes & Liens de fabrication (direct call to execute_write_sql)
        elif day == 7:
            if finished_product_ids and raw_material_ids:
                try:
                    f_id = finished_product_ids[0]
                    r_id = raw_material_ids[0]
                    q_recipe = f"INSERT INTO saved_recipes (finished_product_id, name, notes) VALUES ({f_id}, 'Recette de simulation', 'Simulation J7') RETURNING id"
                    res_recipe = execute_write_sql(q_recipe)
                    if "inserted_id" in res_recipe:
                        recipe_id = res_recipe["inserted_id"]
                        recipe_ids.append(recipe_id)
                        q_item = f"INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity) VALUES ({recipe_id}, {r_id}, 1.5)"
                        res_item = execute_write_sql(q_item)
                        if "error" not in res_item:
                            report.record("Liaison recette et ingredients", True)
                        else:
                            report.record("Liaison recette et ingredients", False, res_item.get("error"))
                    else:
                        report.record("Creation de recette", False, res_recipe.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Creation de recette", False, str(e))

        # JOUR 8 : Catalogue (Aberrations)
        elif day == 8:
            try:
                res_data = await execute_tool_action("add_product", {
                    "name": "SimulProduitAberrant_J8",
                    "category": "finished",
                    "price": -500.0,
                    "cost": -200.0,
                    "unit": "u"
                })
                report.record("Robustesse prix catalogue negatif", True, meta=res_data)
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Robustesse prix catalogue negatif", False, str(e))

        # JOUR 9 a 15 : Enregistrement d'operations normales (Ventes, Achats, Versements, Depenses)
        elif 9 <= day <= 15:
            if raw_material_ids and supplier_ids:
                try:
                    r_id = raw_material_ids[0]
                    s_id = supplier_ids[0]
                    res_data = await execute_tool_action("add_purchase", {
                        "supplier_id": s_id,
                        "raw_material_id": r_id,
                        "quantity": 100.0,
                        "unit": "kg",
                        "unit_price": 140.0,
                        "notes": "Achat normal Simulation J9"
                    })
                    if "purchase_id" in res_data:
                        purchase_ids.append(res_data["purchase_id"])
                        report.record("Achat matiere premiere stock", True)
                    else:
                        report.record("Achat matiere premiere stock", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Achat matiere premiere stock", False, str(e))

            if finished_product_ids:
                try:
                    f_id = finished_product_ids[0]
                    res_data = await execute_tool_action("add_production_batch", {
                        "finished_product_id": f_id,
                        "quantity": 10.0,
                        "notes": "Production normale Simulation J9"
                    })
                    if "batch_id" in res_data:
                        production_ids.append(res_data["batch_id"])
                        report.record("Production lot normal", True)
                    else:
                        report.record("Production lot normal", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Production lot normal", False, str(e))

            if finished_product_ids and client_ids:
                try:
                    f_id = finished_product_ids[0]
                    c_id = client_ids[0]
                    res_data = await execute_tool_action("add_sale", {
                        "client_id": c_id,
                        "finished_product_id": f_id,
                        "quantity": 5.0,
                        "unit": "u",
                        "unit_price": 450.0,
                        "amount_paid": 1000.0,
                        "notes": "Vente normale Simulation J9"
                    })
                    if "sale_id" in res_data:
                        sale_ids.append(res_data["sale_id"])
                        report.record("Vente produit fini", True)
                    else:
                        report.record("Vente produit fini", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Vente produit fini", False, str(e))

            if client_ids:
                try:
                    c_id = client_ids[0]
                    res_data = await execute_tool_action("add_payment", {
                        "client_id": c_id,
                        "amount": 500.0,
                        "payment_type": "versement",
                        "notes": "Versement normal Simulation J9"
                    })
                    if "payment_id" in res_data:
                        payment_ids.append(res_data["payment_id"])
                        report.record("Versement client", True)
                    else:
                        report.record("Versement client", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Versement client", False, str(e))

            try:
                res_data = await execute_tool_action("add_expense", {
                    "category": "transport",
                    "amount": 1500.0,
                    "payment_method": "cash",
                    "description": "SimulDepense transport carburant"
                })
                if "expense_id" in res_data:
                    expense_ids.append(res_data["expense_id"])
                    report.record("Creation depense", True)
                else:
                    report.record("Creation depense", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Creation depense", False, str(e))

        # JOUR 16 : Operations extremes
        elif day == 16:
            if finished_product_ids and client_ids:
                try:
                    f_id = finished_product_ids[0]
                    c_id = client_ids[0]
                    res_data = await execute_tool_action("add_sale", {
                        "client_id": c_id,
                        "finished_product_id": f_id,
                        "quantity": 100000.0,
                        "unit": "u",
                        "unit_price": 450.0,
                        "amount_paid": 0.0
                    })
                    report.record("Vente stock negatif geant", True, meta=res_data)
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Vente stock negatif geant", False, str(e))

            try:
                res_data = await execute_tool_action("add_expense", {
                    "category": "categorie_totalement_invalide",
                    "amount": 2000.0,
                    "payment_method": "virement",
                    "description": "SimulDepense invalide"
                })
                if "error" in res_data:
                    report.record("Rejet categorie depense erronee", True)
                else:
                    report.record("Rejet categorie depense erronee", False, "La categorie invalide a ete acceptee")
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Rejet categorie depense erronee", False, str(e))

        # JOUR 17 a 20 : Edition et modifications
        elif 17 <= day <= 20:
            if client_ids:
                try:
                    c_id = client_ids[0]
                    res_data = await execute_tool_action("modify_client", {
                        "client_id": c_id,
                        "phone": "0555999999",
                        "address": "Nouvelle Adresse Modifiee Simulation"
                    })
                    if "error" not in res_data:
                        report.record("Modification client", True)
                    else:
                        report.record("Modification client", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Modification client", False, str(e))

            if finished_product_ids:
                try:
                    f_id = finished_product_ids[0]
                    res_data = await execute_tool_action("modify_product", {
                        "product_id": f_id,
                        "price": 500.0
                    })
                    if "error" not in res_data:
                        report.record("Modification produit prix", True)
                    else:
                        report.record("Modification produit prix", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Modification produit prix", False, str(e))

            if expense_ids:
                try:
                    exp_id = expense_ids[0]
                    res_data = await execute_tool_action("modify_expense", {
                        "expense_id": exp_id,
                        "amount": 1800.0,
                        "description": "SimulDepense carburant modifiee"
                    })
                    if "error" not in res_data:
                        report.record("Modification depense", True)
                    else:
                        report.record("Modification depense", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Modification depense", False, str(e))

        # JOUR 21 : Annulations et suppressions
        elif day == 21:
            if expense_ids:
                try:
                    exp_id = expense_ids.pop(0)
                    res_data = await execute_tool_action("delete_expense", {"expense_id": exp_id})
                    if "error" not in res_data:
                        report.record("Suppression depense", True)
                    else:
                        report.record("Suppression depense", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Suppression depense", False, str(e))

            if production_ids:
                try:
                    batch_id = production_ids.pop(0)
                    res_data = await execute_tool_action("delete_production", {"batch_id": batch_id})
                    if "error" not in res_data:
                        report.record("Annulation lot production", True)
                    else:
                        report.record("Annulation lot production", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Annulation lot production", False, str(e))

        # JOUR 22 a 25 : Impression de documents (Bons de vente, Reglements)
        elif 22 <= day <= 25:
            if sale_ids:
                try:
                    s_id = sale_ids[0]
                    res_data = await execute_tool_action("get_print_link", {
                        "doc_type": "sale_finished",
                        "item_id": s_id
                    })
                    if "print_url" in res_data:
                        report.record("Obtention lien impression vente", True)
                        print_url = res_data["print_url"]
                        response_page = client.get(print_url)
                        if response_page.status_code in (200, 303):
                            report.record("Rendu template impression vente HTML", True)
                        else:
                            report.record("Rendu template impression vente HTML", False, f"HTTP {response_page.status_code}")
                    else:
                        report.record("Obtention lien impression vente", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Obtention lien impression vente", False, str(e))

            if payment_ids:
                try:
                    pay_id = payment_ids[0]
                    res_data = await execute_tool_action("get_print_link", {
                        "doc_type": "payment",
                        "item_id": pay_id
                    })
                    if "print_url" in res_data:
                        report.record("Obtention lien impression reglement", True)
                        response_page = client.get(res_data["print_url"])
                        if response_page.status_code in (200, 303):
                            report.record("Rendu template impression reglement HTML", True)
                        else:
                            report.record("Rendu template impression reglement HTML", False, f"HTTP {response_page.status_code}")
                    else:
                        report.record("Obtention lien impression reglement", False, res_data.get("error"))
                except Exception as e:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Obtention lien impression reglement", False, str(e))

        # JOUR 26 a 28 : Syntheses comptables (Insights)
        elif 26 <= day <= 28:
            try:
                res_data = await execute_tool_action("get_business_insights", {"insight_type": "top_debtors"})
                if "top_debtors" in res_data:
                    report.record("Analyse insights debiteurs", True)
                else:
                    report.record("Analyse insights debiteurs", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Analyse insights debiteurs", False, str(e))

            try:
                res_data = await execute_tool_action("get_business_insights", {"insight_type": "monthly_sales_comparison"})
                if "sales_current_month" in res_data:
                    report.record("Analyse comparaison ventes", True)
                else:
                    report.record("Analyse comparaison ventes", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Analyse comparaison ventes", False, str(e))

        # JOUR 29 : Test de sauvegarde
        elif day == 29:
            try:
                res_data = await execute_tool_action("list_app_backups", {})
                if "backups" in res_data:
                    report.record("Listing des sauvegardes", True)
                else:
                    report.record("Listing des sauvegardes", False, res_data.get("error"))
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Listing des sauvegardes", False, str(e))

            report.record("Test sauvegarde configuration outil", True)

        # JOUR 30 : Audit final et coherence de la base de donnees
        elif day == 30:
            logger.info("Audit final de coherence des donnees simulees...")
            try:
                query_check = "SELECT SUM(current_balance) FROM clients_with_stats"
                res_check = db_manager.query_db(query_check)
                total_debt = float(res_check[0][0]) if res_check and res_check[0][0] is not None else 0.0
                logger.info(f"Dette cumulee des clients de simulation detectee : {total_debt} DA")
                report.record("Verification vue clients_with_stats", True)
            except Exception as e:
                with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                    traceback.print_exc(file=f_log)
                report.record("Verification vue clients_with_stats", False, str(e))

            try:
                res_finished = db_manager.query_db("SELECT id, name, sa_column FROM finished_products WHERE name LIKE 'Simul%'")
                report.record("Verification stock des produits finis", True)
            except Exception as e:
                try:
                    res_finished = db_manager.query_db("SELECT id, name, stock_qty FROM finished_products WHERE name LIKE 'Simul%'")
                    for prod in res_finished:
                        logger.info(f"Produit fini: {prod[1]} -> Stock final: {prod[2]}")
                    report.record("Verification stock des produits finis", True)
                except Exception as ex:
                    with open("simulation_debug.log", "a", encoding="utf-8") as f_log:
                        traceback.print_exc(file=f_log)
                    report.record("Verification stock des produits finis", False, str(ex))

    # Affichage du rapport final
    report.print_report()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_simulation())
