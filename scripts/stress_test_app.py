#!/usr/bin/env python
"""
Stress and Extreme Edge Case Testing Script for FABouanes application.
Tests boundary limits, numeric overflows, string size bloating, SQL injections, date limits, and concurrency race conditions.
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
import httpx

# Configure stdout encoding to utf-8 if not already
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fabouanes.stress")

# Setup project root path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Setup mock objects
mock_user = {"id": 1, "username": "stress_admin", "role": "admin", "is_active": 1}

async def async_noop(*args, **kwargs):
    pass

# Import the modules first so they are present in sys.modules before patching
from app.main import app
from app.web import client_pages, contacts_pages, operations_pages, production_pages, report_pages
from app.modules.sales import web as sales_web
from app.modules.purchases import web as purchases_web
from app.modules.payments import web as payments_web
from app.modules.expenses import web as expenses_web
from app.modules.catalog import web as catalog_web
from app.web import deps

# Start the patchers now that the modules are fully loaded
patchers = [
    patch("app.web.deps.require_permission", return_value=None),
    patch("app.web.deps.get_current_user", return_value=mock_user),
    patch("app.web.deps.csrf_protect", async_noop),
    patch("app.web.deps.verify_csrf_token", return_value=None),
    patch("app.web.deps.load_user_from_session", return_value=mock_user),
    
    # Patch direct references in page modules
    patch("app.web.client_pages.require_permission", return_value=None),
    patch("app.web.client_pages.csrf_protect", async_noop),
    patch("app.web.client_pages.get_current_user", return_value=mock_user),
    patch("app.web.client_pages.load_user_from_session", return_value=mock_user),
    
    patch("app.web.contacts_pages.require_permission", return_value=None),
    patch("app.web.contacts_pages.csrf_protect", async_noop),
    patch("app.web.contacts_pages.get_current_user", return_value=mock_user),
    
    patch("app.web.operations_pages.require_permission", return_value=None),
    patch("app.web.operations_pages.csrf_protect", async_noop),
    patch("app.web.operations_pages.get_current_user", return_value=mock_user),
    
    patch("app.web.production_pages.require_permission", return_value=None),
    patch("app.web.production_pages.csrf_protect", async_noop),
    patch("app.web.production_pages.get_current_user", return_value=mock_user),
    
    patch("app.web.report_pages.require_permission", return_value=None),
    patch("app.web.report_pages.csrf_protect", async_noop),
    patch("app.web.report_pages.get_current_user", return_value=mock_user),
    
    patch("app.modules.sales.web.require_permission", return_value=None),
    patch("app.modules.sales.web.csrf_protect", async_noop),
    patch("app.modules.sales.web.get_current_user", return_value=mock_user),
    
    patch("app.modules.purchases.web.require_permission", return_value=None),
    patch("app.modules.purchases.web.csrf_protect", async_noop),
    patch("app.modules.purchases.web.get_current_user", return_value=mock_user),
    
    patch("app.modules.payments.web.require_permission", return_value=None),
    patch("app.modules.payments.web.csrf_protect", async_noop),
    patch("app.modules.payments.web.get_current_user", return_value=mock_user),
    
    patch("app.modules.expenses.web.require_permission", return_value=None),
    patch("app.modules.expenses.web.csrf_protect", async_noop),
    patch("app.modules.expenses.web.get_current_user", return_value=mock_user),
    
    patch("app.modules.catalog.web.require_permission", return_value=None),
    patch("app.modules.catalog.web.csrf_protect", async_noop),
    patch("app.modules.catalog.web.get_current_user", return_value=mock_user),
]

for p in patchers:
    try:
        p.start()
    except Exception:
        pass

# Override all verify_csrf_token dependencies on routes dynamically using robust matching
for route in app.routes:
    if hasattr(route, "dependencies"):
        for dep in route.dependencies:
            dep_fn = dep.dependency
            name = getattr(dep_fn, "__name__", "")
            if name == "verify_csrf_token" or "verify_csrf_token" in str(dep_fn) or "verify_csrf_token" in str(getattr(dep_fn, "func", "")):
                app.dependency_overrides[dep_fn] = lambda: None

from fastapi.testclient import TestClient
from app.core.db_helpers import db_manager
from app.modules.assistant.service import execute_tool_action, execute_write_sql
from sqlmodel import select, text

# Configure dependency overrides for JWT auth too
from app.core.jwt_auth import get_current_user_id
app.dependency_overrides[get_current_user_id] = lambda: 1

client = TestClient(app)

class StressTestReport:
    def __init__(self):
        self.tests_run = 0
        self.success_count = 0
        self.failures = []

    def record_result(self, name: str, success: bool, details: str = ""):
        self.tests_run += 1
        safe_details = str(details).encode("ascii", errors="replace").decode("ascii")
        if success:
            self.success_count += 1
            logger.info(f"[PASS] {name} - {safe_details}")
        else:
            self.failures.append((name, safe_details))
            logger.error(f"[FAIL] {name} - {safe_details}")

    def print_summary(self):
        print("\n" + "=" * 60)
        print("[RAPPORT DU STRESS TESTING - RÉSISTANCES ET CRASH LIMITES]")
        print("=" * 60)
        print(f"Total des tests exécutés : {self.tests_run}")
        print(f"Réussites (Comportement sain/Géré) : {self.success_count}")
        print(f"Échecs (Crashes 500 / Bugs non gérés) : {len(self.failures)}")
        
        if self.failures:
            print("\n[CRASHES ET ANOMALIES DÉTECTÉES] :")
            for name, details in self.failures:
                print(f" - {name} : {details}")
        else:
            print("\n[EXCELLENT] L'application résiste parfaitement à toutes les entrées irréelles.")
        print("=" * 60 + "\n")

async def test_numeric_overflows(report):
    logger.info("Lancement du test 1 : Débordements Numériques (Overflows)...")
    
    # Clean old client
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM clients WHERE name = 'Stress_Client_Huge_Credit'")

    # 1.1. Client avec un crédit d'ouverture gigantesque (dépasse les limites de la base)
    try:
        response = client.post("/clients", data={
            "name": "Stress_Client_Huge_Credit",
            "phone": "0555123456",
            "address": "Adresse Test",
            "opening_credit": "999999999999999999.99",  # Débordement
            "notes": "Stress test"
        })
        # Check if the page returned a validation/friendly error, or crashed with 500
        if response.status_code == 500:
            report.record_result("Credit client géant", False, "Levée d'une erreur 500 serveur")
        elif "dépasse les limites" in response.text.lower() or response.status_code in (400, 303):
            report.record_result("Credit client géant", True, "Le débordement numérique est proprement intercepté et affiché en message amical")
        else:
            report.record_result("Credit client géant", True, f"Rejeté ou géré sans crash (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Credit client géant", False, f"Crash inattendu : {e}")

    # 1.2. Catalogue avec un prix de vente irréel
    try:
        response = client.post("/catalog/new", data={
            "category": "finished",
            "name": "Stress_Produit_Huge_Price",
            "sale_price": "9999999999999999.00",
            "avg_cost": "1.00",
            "default_unit": "u"
        })
        if response.status_code == 500:
            report.record_result("Prix produit géant", False, "Levée d'une erreur 500 serveur")
        else:
            report.record_result("Prix produit géant", True, f"Géré sans crash (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Prix produit géant", False, f"Crash inattendu : {e}")

async def test_string_bloating(report):
    logger.info("Lancement du test 2 : Surcharges textuelles (Payload Bloating)...")
    
    # Clean old client
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM clients WHERE name LIKE 'A%' AND length(name) = 100000")

    # 2.1. Client avec un nom de 100 000 caractères
    huge_name = "A" * 100000
    try:
        response = client.post("/clients", data={
            "name": huge_name,
            "phone": "0555123456",
            "address": "Adresse Test",
            "opening_credit": "0.0",
            "notes": "Stress test string bloating"
        })
        if response.status_code == 500:
            report.record_result("Nom client 100k chars", False, "Levée d'une erreur 500 serveur")
        else:
            report.record_result("Nom client 100k chars", True, f"Géré sans crash (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Nom client 100k chars", False, f"Crash : {e}")

    # 2.2. Dépense avec des notes de 500 000 caractères
    huge_notes = "B" * 500000
    try:
        response = client.post("/expenses/new", data={
            "category": "autre",
            "amount": "100.0",
            "payment_method": "cash",
            "description": huge_notes
        })
        if response.status_code == 500:
            report.record_result("Notes dépense 500k chars", False, "Levée d'une erreur 500 serveur")
        else:
            report.record_result("Notes dépense 500k chars", True, f"Géré sans crash (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Notes dépense 500k chars", False, f"Crash : {e}")

async def test_injections_and_security(report):
    logger.info("Lancement du test 3 : Injections SQL et XSS...")
    
    sql_injection_payload = "Ahmed'); DROP TABLE clients; --"
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM clients WHERE name = %s", (sql_injection_payload,))

    # 3.1. SQL Injection dans le champ nom d'un client
    try:
        response = client.post("/clients", data={
            "name": sql_injection_payload,
            "phone": "0555111111",
            "address": "Injection test",
            "opening_credit": "100.0",
            "notes": ""
        })
        # Check if client was inserted as-is (secured via parameters)
        with db_manager.db_transaction() as conn:
            res = conn.execute("SELECT COUNT(*) FROM clients WHERE name = %s", (sql_injection_payload,)).fetchone()
            inserted_count = res[0] if res else 0
            
        if inserted_count == 1:
            report.record_result("Securite SQL Injection Insertion", True, "Le payload a été inséré de manière sécurisée en tant que texte")
        else:
            report.record_result("Securite SQL Injection Insertion", False, f"Le payload n'a pas été retrouvé en base (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Securite SQL Injection Insertion", False, f"Crash ou erreur : {e}")

    # 3.2. Script XSS injecté dans le champ description de dépense
    xss_payload = "<script>alert('HACKED')</script>"
    try:
        client.post("/expenses/new", data={
            "category": "autre",
            "amount": "50.0",
            "payment_method": "cash",
            "description": xss_payload
        })
        
        # Charger la page des dépenses et voir si le script XSS est échappé ou exécuté brut
        response = client.get("/expenses")
        if xss_payload in response.text:
            # Check if it is escaped in HTML format (e.g. &lt;script&gt;)
            if "&lt;script&gt;" in response.text or "lt;script" in response.text:
                report.record_result("Securite XSS Dépense", True, "Le script XSS a été correctement échappé en entités HTML")
            else:
                report.record_result("Securite XSS Dépense", False, "Le script XSS est rendu sous forme brute dans le HTML (Vulnérabilité XSS !)")
        else:
            report.record_result("Securite XSS Dépense", True, "Le script XSS n'est pas présent sous sa forme brute exécutable")
    except Exception as e:
        report.record_result("Securite XSS Dépense", False, f"Crash : {e}")

async def test_date_limits(report):
    logger.info("Lancement du test 4 : Limites temporelles (Dates invalides)...")
    
    # 4.1. Date du futur extrême
    try:
        response = client.post("/expenses/new", data={
            "date": "9999-12-31",
            "category": "autre",
            "amount": "250.0",
            "payment_method": "cash",
            "description": "Futur"
        })
        report.record_result("Date du futur lointain", True, f"Retour HTTP {response.status_code}")
    except Exception as e:
        report.record_result("Date du futur lointain", False, f"Crash : {e}")

    # 4.2. Date invalide (30 février)
    try:
        response = client.post("/expenses/new", data={
            "date": "2026-02-30",
            "category": "autre",
            "amount": "250.0",
            "payment_method": "cash",
            "description": "30 Fevrier"
        })
        if response.status_code in (400, 422, 303) or "invalide" in response.text:
            report.record_result("Date invalide (30 Fevrier)", True, f"Rejet/Redirection de validation propre (HTTP {response.status_code})")
        else:
            report.record_result("Date invalide (30 Fevrier)", False, f"Accepté ou non géré proprement (HTTP {response.status_code})")
    except Exception as e:
        report.record_result("Date invalide (30 Fevrier)", False, f"Crash : {e}")

async def test_concurrency_locks(report):
    logger.info("Lancement du test 5 : Concurrence et Verrous de Base de Données...")
    
    # Create a test client first
    c_name = "Stress_Client_Concurrence"
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM clients WHERE name = %s", (c_name,))
        res = conn.execute("INSERT INTO clients (name, phone, address, notes) VALUES (%s, '000000', '', '') RETURNING id", (c_name,))
        client_id = res.fetchone()[0]
    
    errors = []
    
    # We use httpx.ASGITransport for newer httpx versions
    async def make_request(worker_id):
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
                resp = await ac.post("/payments/new", data={
                    "client_id": str(client_id),
                    "amount": "10.0",
                    "payment_type": "versement",
                    "notes": f"Concurrent task {worker_id}"
                })
                if resp.status_code == 500:
                    errors.append(f"Task {worker_id} got HTTP 500: {resp.text}")
        except Exception as e:
            errors.append(f"Task {worker_id} crashed: {e}")

    # Launch 15 concurrent tasks
    tasks = [make_request(i) for i in range(15)]
    await asyncio.gather(*tasks)
        
    if errors:
        report.record_result("Transactions concurrentes simultanées", False, f"Des erreurs de concurrence ont été détectées : {errors[:3]}")
    else:
        report.record_result("Transactions concurrentes simultanées", True, "15 paiements simultanés gérés sans verrous ni crash 500")

    # Clean up stress data
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM client_history WHERE client_id = %s", (client_id,))
        conn.execute("DELETE FROM payments WHERE client_id = %s", (client_id,))
        conn.execute("DELETE FROM clients WHERE id = %s", (client_id,))

async def main():
    report = StressTestReport()
    
    await test_numeric_overflows(report)
    await test_string_bloating(report)
    await test_injections_and_security(report)
    await test_date_limits(report)
    await test_concurrency_locks(report)
    
    report.print_summary()
    
    # Cleanup stress client
    sql_injection_payload = "Ahmed'); DROP TABLE clients; --"
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM clients WHERE name = %s", (sql_injection_payload,))
        conn.execute("DELETE FROM clients WHERE name LIKE 'A%' AND length(name) = 100000")

    if len(report.failures) > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
