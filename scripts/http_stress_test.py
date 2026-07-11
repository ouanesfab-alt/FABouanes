#!/usr/bin/env python
"""
=============================================================================
FABouanes — HTTP Stress Test Complet (15 Modules, 10-20 répétitions)
=============================================================================
Simule de vraies sessions navigateur via httpx :
  - Connexion / déconnexion réelles avec cookies de session
  - Extraction et injection automatique du token CSRF
  - Tests de toutes les routes GET et POST
  - Détection des erreurs HTTP 4xx/5xx + erreurs HTML dans le corps
  - Nettoyage complet des données de test en fin de script

Utilisation :
  python scripts/http_stress_test.py [--url http://127.0.0.1:8000] [--repeat 10]
"""

from __future__ import annotations
import asyncio
import sys
import re
import json
import time
import logging
import argparse
import io
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

# UTF-8 Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"c:\Users\massi\Downloads\FABouanes-main"
sys.path.insert(0, PROJECT_ROOT)

try:
    import httpx
except ImportError:
    print("httpx manquant. Installation...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("http_stress_test.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("fab.stresstest")

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "0000"


@dataclass
class TestResult:
    module: str
    task: str
    iteration: int
    status_code: int
    ok: bool
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class TestReport:
    results: List[TestResult] = field(default_factory=list)

    def add(self, r: TestResult):
        self.results.append(r)
        if r.ok:
            logger.info(f"  ✅ [{r.module}] {r.task} (#{r.iteration}) — {r.status_code} ({r.duration_ms:.0f}ms)")
        else:
            logger.error(f"  ❌ [{r.module}] {r.task} (#{r.iteration}) — {r.status_code}: {r.error}")

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.ok)
        failed = total - passed
        by_module: Dict[str, Dict] = defaultdict(lambda: {"pass": 0, "fail": 0})
        for r in self.results:
            if r.ok:
                by_module[r.module]["pass"] += 1
            else:
                by_module[r.module]["fail"] += 1

        lines = [
            "",
            "=" * 80,
            "  RAPPORT FINAL DU STRESS TEST HTTP",
            "=" * 80,
            f"  Total : {total} | ✅ Réussis : {passed} | ❌ Échoués : {failed}",
            "",
            "  Détail par module :",
        ]
        for mod, counts in sorted(by_module.items()):
            status = "✅" if counts["fail"] == 0 else "❌"
            lines.append(f"    {status} {mod:<40} Pass:{counts['pass']:3}  Fail:{counts['fail']:3}")

        if failed > 0:
            lines += ["", "  Erreurs détectées :"]
            for r in self.results:
                if not r.ok:
                    lines.append(f"    ❌ [{r.module}] {r.task} (#{r.iteration}): {r.error[:120]}")

        lines.append("=" * 80)
        return "\n".join(lines)


def extract_csrf(html: str) -> Optional[str]:
    """Extrait le token CSRF depuis le HTML d'une page."""
    # Méthode 1: meta tag
    m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    # Méthode 2: input hidden
    m = re.search(r'<input[^>]+name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    # Méthode 3: window.__CSRF__
    m = re.search(r'window\.__CSRF__\s*=\s*["\']([^"\']+)', html)
    if m:
        return m.group(1)
    return None


def has_error_in_body(html: str) -> Tuple[bool, str]:
    """Vérifie si la réponse HTML contient une trace d'erreur ou une page d'erreur serveur."""
    lower = html.lower()
    # Erreurs critiques
    for pattern in ["traceback (most recent call last)", "internal server error",
                     "500 internal server error", "unhandled exception",
                     "operationalerror", "programmingeerror"]:
        if pattern in lower:
            # Trouve le contexte
            idx = lower.find(pattern)
            snippet = html[max(0, idx-30):idx+120].strip()
            return True, f"Erreur dans le corps HTML: ...{snippet}..."
    return False, ""


class FABClient:
    """Client HTTP avec session persistante, gestion CSRF et auth automatique."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "FAB-StressTest/1.0"},
        )
        self._csrf_token: Optional[str] = None
        self._logged_in = False

    async def close(self):
        await self.client.aclose()

    async def get(self, path: str, **kwargs) -> httpx.Response:
        r = await self.client.get(path, **kwargs)
        # Refresh CSRF from any page we load
        if r.headers.get("content-type", "").startswith("text/html"):
            tok = extract_csrf(r.text)
            if tok:
                self._csrf_token = tok
        return r

    async def post(self, path: str, data: Optional[dict] = None,
                   json_body: Optional[dict] = None, files=None, **kwargs) -> httpx.Response:
        """POST avec injection automatique du token CSRF."""
        # Si on n'a pas de token, on GET la page d'abord
        if not self._csrf_token:
            await self.get(path.replace("/new", "").replace("/edit", "") or "/")

        if json_body is not None:
            headers = {
                "X-CSRFToken": self._csrf_token or "",
                "Content-Type": "application/json",
            }
            r = await self.client.post(path, json=json_body, headers=headers, **kwargs)
        else:
            if data is None:
                data = {}
            data.setdefault("csrf_token", self._csrf_token or "")
            if files:
                r = await self.client.post(path, data=data, files=files, **kwargs)
            else:
                r = await self.client.post(path, data=data, **kwargs)

        if r.headers.get("content-type", "").startswith("text/html"):
            tok = extract_csrf(r.text)
            if tok:
                self._csrf_token = tok
        return r

    async def login(self) -> bool:
        """Se connecte avec admin/0000 et établit la session."""
        for attempt in range(3):
            # 1. GET /login pour avoir le CSRF token
            r = await self.get("/login")
            if r.status_code not in (200, 302, 303):
                logger.error(f"Login GET failed: {r.status_code}")
                return False

            tok = extract_csrf(r.text)
            if tok:
                self._csrf_token = tok

            # 2. POST /login
            r = await self.post("/login", data={
                "username": USERNAME,
                "password": PASSWORD,
                "csrf_token": self._csrf_token or "",
            })

            # 429 Too Many Requests — attendre 65 secondes
            if r.status_code == 429:
                wait_s = 65
                logger.warning(f"  ⏳ Rate limit atteint sur /login (429). Attente {wait_s}s... (tentative {attempt+1}/3)")
                await asyncio.sleep(wait_s)
                continue

            # Si redirigé vers / ou /change-password → success
            if r.status_code in (200, 302, 303):
                final_url = str(r.url)
                if "/login" not in final_url:
                    self._logged_in = True
                    logger.info(f"🔑 Connexion réussie → {final_url}")
                    return True

            # Cherche le message d'erreur dans le HTML
            if "invalide" in r.text.lower() or "incorrect" in r.text.lower():
                logger.error("Login échoué : identifiants invalides")
            else:
                logger.error(f"Login échoué: status={r.status_code} url={r.url}")
            return False

        logger.error("Login échoué après 3 tentatives (rate limit persistant).")
        return False

    async def logout(self) -> bool:
        r = await self.get("/logout")
        self._logged_in = False
        self._csrf_token = None
        return r.status_code in (200, 302, 303)


# =============================================================================
# HELPERS : Créer les entités de base nécessaires aux tests
# =============================================================================

_state: Dict[str, Any] = {}  # IDs créés dynamiquement


async def ensure_raw_material(client: FABClient) -> Optional[int]:
    """Crée une matière première de test et retourne son ID."""
    if "raw_id" in _state:
        return _state["raw_id"]
    await client.get("/catalog/new?kind=raw")
    r = await client.post("/catalog/new", data={
        "kind": "raw",
        "name": "Orge HTTP Test",
        "unit": "kg",
        "stock_qty": "5000",
        "avg_cost": "42.50",
        "alert_threshold": "0",
        "threshold_qty": "500",
    })
    if r.status_code in (200, 302, 303):
        from app.core.db_helpers import query_db
        rows = query_db("SELECT id FROM raw_materials WHERE name='Orge HTTP Test' ORDER BY id DESC LIMIT 1")
        if rows:
            _state["raw_id"] = rows[0]["id"]
            logger.info(f"  📦 Matière 'Orge HTTP Test' créée (id={_state['raw_id']})")
            return _state["raw_id"]
    return None


async def ensure_finished_product(client: FABClient) -> Optional[int]:
    if "prod_id" in _state:
        return _state["prod_id"]
    await client.get("/catalog/new?kind=finished")
    r = await client.post("/catalog/new", data={
        "kind": "finished",
        "name": "Aliment HTTP Test",
        "default_unit": "kg",
        "stock_qty": "2000",
        "sale_price": "78.00",
        "avg_cost": "55.00",
        "alert_threshold": "0",
        "threshold_qty": "100",
    })
    if r.status_code in (200, 302, 303):
        from app.core.db_helpers import query_db
        rows = query_db("SELECT id FROM finished_products WHERE name='Aliment HTTP Test' ORDER BY id DESC LIMIT 1")
        if rows:
            _state["prod_id"] = rows[0]["id"]
            logger.info(f"  📦 Produit 'Aliment HTTP Test' créé (id={_state['prod_id']})")
            return _state["prod_id"]
    return None


async def ensure_client(client: FABClient) -> Optional[int]:
    if "client_id" in _state:
        return _state["client_id"]
    await client.get("/contacts/new?kind=client")
    r = await client.post("/contacts/clients/new", data={
        "name": "Client HTTP Test",
        "phone": "0555010203",
        "address": "10 Rue du Test",
        "notes": "Client de stress test HTTP",
        "opening_credit": "0",
    })
    if r.status_code in (200, 302, 303):
        from app.core.db_helpers import query_db
        rows = query_db("SELECT id FROM clients WHERE name='Client HTTP Test' ORDER BY id DESC LIMIT 1")
        if rows:
            _state["client_id"] = rows[0]["id"]
            logger.info(f"  👤 Client 'Client HTTP Test' créé (id={_state['client_id']})")
            return _state["client_id"]
    return None


async def ensure_supplier(client: FABClient) -> Optional[int]:
    if "supplier_id" in _state:
        return _state["supplier_id"]
    await client.get("/contacts/new?kind=supplier")
    r = await client.post("/contacts/suppliers/new", data={
        "name": "Fournisseur HTTP Test",
        "phone": "0666010203",
        "address": "20 Zone Industrielle",
        "notes": "Fournisseur de stress test HTTP",
    })
    if r.status_code in (200, 302, 303):
        from app.core.db_helpers import query_db
        rows = query_db("SELECT id FROM suppliers WHERE name='Fournisseur HTTP Test' ORDER BY id DESC LIMIT 1")
        if rows:
            _state["supplier_id"] = rows[0]["id"]
            logger.info(f"  🏭 Fournisseur 'Fournisseur HTTP Test' créé (id={_state['supplier_id']})")
            return _state["supplier_id"]
    return None


# =============================================================================
# MODULES DE TEST
# =============================================================================

async def check(client: FABClient, module: str, task: str, iteration: int,
                method: str, path: str, data: Optional[dict] = None,
                expected_codes=(200, 302, 303), report: TestReport = None) -> bool:
    """Exécute un test HTTP et enregistre le résultat."""
    start = time.monotonic()
    try:
        if method == "GET":
            r = await client.get(path)
        else:
            r = await client.post(path, data=data)
        elapsed = (time.monotonic() - start) * 1000

        ok = r.status_code in expected_codes
        error = ""

        if ok:
            err_found, err_msg = has_error_in_body(r.text)
            if err_found:
                ok = False
                error = err_msg

        if not ok and not error:
            # Tente d'extraire le message d'erreur depuis le HTML
            m = re.search(r'class=["\'][^"\']*alert[^"\']*["\'][^>]*>(.*?)</div>', r.text, re.DOTALL)
            if m:
                error = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:150]
            else:
                error = f"HTTP {r.status_code}"

        result = TestResult(module=module, task=task, iteration=iteration,
                           status_code=r.status_code, ok=ok, error=error,
                           duration_ms=elapsed)
        report.add(result)
        return ok

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        result = TestResult(module=module, task=task, iteration=iteration,
                           status_code=0, ok=False, error=str(e)[:150],
                           duration_ms=elapsed)
        report.add(result)
        return False


# =============================================================================
# MODULE 1 — Authentification
# =============================================================================
async def test_module1_auth(report: TestReport, repeat: int):
    logger.info("\n🔑 MODULE 1 : Authentification & Sécurité")
    for i in range(1, repeat + 1):
        c = FABClient(BASE_URL)
        ok = await c.login()
        r = TestResult("M1-Auth", "Se connecter", i, 200 if ok else 401, ok,
                       "" if ok else "Login échoué")
        report.add(r)
        if ok:
            # Test page changement de mot de passe (GET)
            await check(c, "M1-Auth", "Page change-password", i, "GET", "/change-password", report=report)
            # Test déconnexion
            lo = await c.logout()
            r2 = TestResult("M1-Auth", "Se déconnecter", i, 200 if lo else 500, lo,
                            "" if lo else "Logout échoué")
            report.add(r2)
        await c.close()
        await asyncio.sleep(0.3)

    # Test QR Code mobile (GET uniquement)
    c = FABClient(BASE_URL)
    await c.login()
    for i in range(1, min(repeat, 5) + 1):
        await check(c, "M1-Auth", "Page connexion mobile QR", i, "GET", "/mobile-connect", report=report)
    await c.close()


# =============================================================================
# MODULE 2 — Tableau de bord
# =============================================================================
async def test_module2_dashboard(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n📊 MODULE 2 : Tableau de Bord & Statistiques")
    for i in range(1, repeat + 1):
        await check(client, "M2-Dashboard", "Indicateurs du jour (GET /)", i, "GET", "/", report=report)
        await check(client, "M2-Dashboard", "Filtre Aujourd'hui", i, "GET", "/?period=today", report=report)
        await check(client, "M2-Dashboard", "Filtre Ce Mois", i, "GET", "/?period=month", report=report)
        await check(client, "M2-Dashboard", "Filtre Cette Année", i, "GET", "/?period=year", report=report)
        await check(client, "M2-Dashboard", "Alertes de stock (dashboard)", i, "GET", "/", report=report)
        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 3 — Catalogue
# =============================================================================
async def test_module3_catalog(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n📦 MODULE 3 : Catalogue & Fiches Articles")
    raw_id = await ensure_raw_material(client)
    prod_id = await ensure_finished_product(client)
    today = date.today().isoformat()

    for i in range(1, repeat + 1):
        await check(client, "M3-Catalog", "Liste catalogue (tous)", i, "GET", "/catalog", report=report)
        await check(client, "M3-Catalog", "Filtre matières premières", i, "GET", "/catalog?kind=raw", report=report)
        await check(client, "M3-Catalog", "Filtre produits finis", i, "GET", "/catalog?kind=finished", report=report)
        await check(client, "M3-Catalog", "Formulaire nouveau article (GET)", i, "GET", "/catalog/new?kind=raw", report=report)

        # Créer une matière temporaire
        await client.get("/catalog/new?kind=raw")
        await check(client, "M3-Catalog", "Créer matière première", i, "POST", "/catalog/new",
                    data={"kind": "raw", "name": f"Maïs Test {i}", "unit": "kg",
                          "stock_qty": "1000", "avg_cost": "38.00",
                          "alert_threshold": "0", "threshold_qty": "200"},
                    report=report)

        # Créer un produit fini temporaire
        await client.get("/catalog/new?kind=finished")
        await check(client, "M3-Catalog", "Créer produit fini", i, "POST", "/catalog/new",
                    data={"kind": "finished", "name": f"Aliment Bovin Test {i}", "default_unit": "kg",
                          "stock_qty": "500", "sale_price": "85.00", "avg_cost": "60.00",
                          "alert_threshold": "0", "threshold_qty": "50"},
                    report=report)

        if raw_id:
            # Modifier une matière (seuil d'alerte)
            await client.get(f"/catalog/raw/{raw_id}/edit")
            await check(client, "M3-Catalog", "Modifier seuil alerte matière", i, "POST",
                        f"/catalog/raw/{raw_id}/edit",
                        data={"name": "Orge HTTP Test", "unit": "kg",
                              "alert_threshold": "1", "threshold_qty": f"{400 + i}",
                              "avg_cost": "42.50", "sale_price": "0"},
                        report=report)

            # Historique mouvements de stock
            await check(client, "M3-Catalog", "Fiche historique stock matière", i, "GET",
                        f"/catalog/raw/{raw_id}/history", report=report)

        if prod_id:
            await client.get(f"/catalog/products/{prod_id}/edit")
            await check(client, "M3-Catalog", "Modifier produit fini", i, "POST",
                        f"/catalog/products/{prod_id}/edit",
                        data={"name": "Aliment HTTP Test", "default_unit": "kg",
                              "sale_price": f"{78.0 + i}", "avg_cost": "55.00",
                              "alert_threshold": "0", "threshold_qty": "100"},
                        report=report)

            await check(client, "M3-Catalog", "Fiche historique stock produit fini", i, "GET",
                        f"/catalog/products/{prod_id}/history", report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 4 — Ventes
# =============================================================================
async def test_module4_sales(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n🛒 MODULE 4 : Ventes & Facturation")
    client_id = await ensure_client(client)
    prod_id = await ensure_finished_product(client)
    raw_id = await ensure_raw_material(client)
    today = date.today().isoformat()

    for i in range(1, repeat + 1):
        await check(client, "M4-Sales", "Page nouvelle vente (GET)", i, "GET",
                    "/operations/sales/new", report=report)

        # Vente produit fini
        if prod_id and client_id:
            await client.get("/operations/sales/new")
            await check(client, "M4-Sales", "Enregistrer vente produit fini", i, "POST",
                        "/operations/sales/new",
                        data={
                            "client_id": str(client_id),
                            "sale_date": today,
                            "notes": f"Stress test vente #{i}",
                            "item_key": f"finished:{prod_id}",
                            "quantity": "50",
                            "unit": "kg",
                            "unit_price": "78.00",
                        },
                        report=report)

        # Vente matière première (raw)
        if raw_id and client_id:
            await client.get("/operations/sales/new")
            await check(client, "M4-Sales", "Enregistrer vente matière première", i, "POST",
                        "/operations/sales/new",
                        data={
                            "client_id": str(client_id),
                            "sale_date": today,
                            "notes": f"Stress test vente MP #{i}",
                            "item_key": f"raw:{raw_id}",
                            "quantity": "20",
                            "unit": "kg",
                            "unit_price": "50.00",
                        },
                        report=report)

        # Liste des ventes
        await check(client, "M4-Sales", "Liste ventes (GET /sales)", i, "GET",
                    "/sales", report=report)

        # PDF BL
        from app.core.db_helpers import query_db
        docs = query_db("SELECT id FROM sale_documents ORDER BY id DESC LIMIT 1")
        if docs:
            doc_id = docs[0]["id"]
            await check(client, "M4-Sales", "Visualiser PDF vente", i, "GET",
                        f"/print/sale/{doc_id}", report=report)
            await check(client, "M4-Sales", "Télécharger PDF BL", i, "GET",
                        f"/bons/sale/{doc_id}", report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 5 — Achats
# =============================================================================
async def test_module5_purchases(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n🌾 MODULE 5 : Achats & Approvisionnement")
    supplier_id = await ensure_supplier(client)
    raw_id = await ensure_raw_material(client)
    today = date.today().isoformat()

    for i in range(1, repeat + 1):
        await check(client, "M5-Purchases", "Page nouvel achat (GET)", i, "GET",
                    "/operations/purchases/new", report=report)

        if supplier_id and raw_id:
            await client.get("/operations/purchases/new")
            await check(client, "M5-Purchases", "Enregistrer achat matière", i, "POST",
                        "/operations/purchases/new",
                        data={
                            "supplier_id": str(supplier_id),
                            "purchase_date": today,
                            "notes": f"Stress test achat #{i}",
                            "raw_material_id": f"raw:{raw_id}",
                            "quantity": "200",
                            "unit": "kg",
                            "unit_price": "42.50",
                        },
                        report=report)

        await check(client, "M5-Purchases", "Liste achats (GET)", i, "GET",
                    "/purchases", report=report)

        # PDF BR
        from app.core.db_helpers import query_db
        docs = query_db("SELECT id FROM purchase_documents ORDER BY id DESC LIMIT 1")
        if docs:
            doc_id = docs[0]["id"]
            await check(client, "M5-Purchases", "Visualiser PDF BR", i, "GET",
                        f"/print/purchase/{doc_id}", report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 6 — Règlements
# =============================================================================
async def test_module6_payments(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n💰 MODULE 6 : Règlements & Trésorerie")
    client_id = await ensure_client(client)
    supplier_id = await ensure_supplier(client)
    today = date.today().isoformat()

    for i in range(1, repeat + 1):
        await check(client, "M6-Payments", "Page versement (GET)", i, "GET",
                    "/operations/payments/new?mode=versement", report=report)

        if client_id:
            # Versement
            await client.get("/operations/payments/new?mode=versement")
            await check(client, "M6-Payments", "Enregistrer versement client", i, "POST",
                        "/operations/payments/new",
                        data={
                            "client_id": str(client_id),
                            "payment_type": "versement",
                            "amount": "5000",
                            "payment_date": today,
                            "notes": f"Versement stress test #{i}",
                        },
                        report=report)

            # Avance
            await client.get("/operations/payments/new?mode=avance")
            await check(client, "M6-Payments", "Saisir avance client", i, "POST",
                        "/operations/payments/new",
                        data={
                            "client_id": str(client_id),
                            "payment_type": "avance",
                            "amount": "2000",
                            "payment_date": today,
                            "notes": f"Avance stress test #{i}",
                        },
                        report=report)

        # Paiement fournisseur (utilise la même route avec supplier_id)
        if supplier_id:
            await client.get("/operations/payments/new?mode=versement")
            await check(client, "M6-Payments", "Paiement fournisseur", i, "POST",
                        "/operations/payments/new",
                        data={
                            "supplier_id": str(supplier_id),
                            "payment_type": "versement",
                            "amount": "8500",
                            "payment_date": today,
                            "notes": f"Paiement fournisseur test #{i}",
                        },
                        report=report)

        # Liste paiements
        await check(client, "M6-Payments", "Liste paiements (GET)", i, "GET",
                    "/payments", report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 7 — Dépenses
# =============================================================================
async def test_module7_expenses(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n💸 MODULE 7 : Dépenses & Frais")
    today = date.today().isoformat()
    categories = ["loyer", "salaire", "transport", "telecom", "energie",
                  "impots", "maintenance", "fournitures", "autre"]
    methods = ["cash", "cheque", "virement", "autre"]

    for i in range(1, repeat + 1):
        await check(client, "M7-Expenses", "Liste dépenses (GET)", i, "GET",
                    "/expenses", report=report)
        await check(client, "M7-Expenses", "Page nouvelle dépense (GET)", i, "GET",
                    "/expenses/new", report=report)

        cat = categories[i % len(categories)]
        meth = methods[i % len(methods)]
        await client.get("/expenses/new")
        await check(client, "M7-Expenses", f"Enregistrer dépense [{cat}/{meth}]", i, "POST",
                    "/expenses/new",
                    data={
                        "date": today,
                        "category": cat,
                        "description": f"Dépense stress test #{i} - {cat}",
                        "amount": f"{1000 + i * 100}",
                        "payment_method": meth,
                    },
                    report=report)

        # Modifier la dernière dépense créée
        from app.core.db_helpers import query_db
        rows = query_db(
            "SELECT id FROM expenses WHERE description LIKE '%stress test%' ORDER BY id DESC LIMIT 1"
        )
        if rows:
            exp_id = rows[0]["id"]
            await client.get(f"/expenses/{exp_id}/edit")
            await check(client, "M7-Expenses", "Modifier dépense", i, "POST",
                        f"/expenses/{exp_id}/edit",
                        data={
                            "date": today,
                            "category": cat,
                            "description": f"Dépense modifiée #{i}",
                            "amount": f"{2000 + i * 50}",
                            "payment_method": "cheque",
                        },
                        report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 8 — Stocks
# =============================================================================
async def test_module8_stocks(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n⚙️  MODULE 8 : Ajustement des Stocks")
    raw_id = _state.get("raw_id") or await ensure_raw_material(client)
    prod_id = _state.get("prod_id") or await ensure_finished_product(client)

    for i in range(1, repeat + 1):
        await check(client, "M8-Stocks", "État stock actuel", i, "GET", "/catalog", report=report)

        if raw_id:
            await client.get(f"/catalog/raw/{raw_id}/adjust")
            await check(client, "M8-Stocks", "Ajustement stock matière", i, "POST",
                        f"/catalog/raw/{raw_id}/adjust",
                        data={"new_qty": f"{3000 - i * 10}", "reason": f"Inventaire stress test #{i}"},
                        report=report)
        if prod_id:
            await client.get(f"/catalog/products/{prod_id}/adjust")
            await check(client, "M8-Stocks", "Ajustement stock produit fini", i, "POST",
                        f"/catalog/products/{prod_id}/adjust",
                        data={"new_qty": f"{1500 - i * 5}", "reason": f"Inventaire stress test #{i}"},
                        report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 9 — Production
# =============================================================================
async def test_module9_production(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n🏭 MODULE 9 : Production & Recettes")
    raw_id = _state.get("raw_id") or await ensure_raw_material(client)
    prod_id = _state.get("prod_id") or await ensure_finished_product(client)
    today = date.today().isoformat()

    for i in range(1, repeat + 1):
        await check(client, "M9-Production", "Historique productions (GET)", i, "GET",
                    "/production", report=report)
        await check(client, "M9-Production", "Page nouvelle production (GET)", i, "GET",
                    "/production/new", report=report)

        if raw_id and prod_id:
            await client.get("/production/new")
            r = await check(client, "M9-Production", "Enregistrer lot production", i, "POST",
                            "/production/new",
                            data={
                                "finished_product_id": str(prod_id),
                                "batch_qty": "100",
                                "production_date": today,
                                "production_cost": "3000",
                                "notes": f"Lot stress test #{i}",
                                "recipe_label": f"Recette Test #{i}",
                                f"raw_material_id[{raw_id}]": str(raw_id),
                                f"qty_used[{raw_id}]": "100",
                            },
                            report=report)

            # Suppression du dernier lot créé (test rollback stocks)
            from app.core.db_helpers import query_db
            batches = query_db(
                "SELECT id FROM production_batches WHERE notes LIKE '%stress test%' ORDER BY id DESC LIMIT 1"
            )
            if batches:
                batch_id = batches[0]["id"]
                await check(client, "M9-Production", "Supprimer lot (rollback stocks)", i, "POST",
                            f"/production/{batch_id}/delete",
                            report=report)

        await asyncio.sleep(0.2)


# =============================================================================
# MODULE 10 — Contacts (Clients & Fournisseurs)
# =============================================================================
async def test_module10_contacts(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n👥 MODULE 10 : Annuaire Tiers")
    client_id = _state.get("client_id") or await ensure_client(client)
    supplier_id = _state.get("supplier_id") or await ensure_supplier(client)

    for i in range(1, repeat + 1):
        await check(client, "M10-Contacts", "Liste contacts (tous)", i, "GET", "/contacts", report=report)
        await check(client, "M10-Contacts", "Filtrer clients", i, "GET", "/contacts?kind=client", report=report)
        await check(client, "M10-Contacts", "Filtrer fournisseurs", i, "GET", "/contacts?kind=supplier", report=report)
        await check(client, "M10-Contacts", "Rechercher contact par nom", i, "GET",
                    "/contacts?search=HTTP+Test", report=report)
        await check(client, "M10-Contacts", "Rechercher contact par téléphone", i, "GET",
                    "/contacts?search=0555010203", report=report)

        # Modifier le client
        if client_id:
            await client.get(f"/clients/{client_id}/edit")
            await check(client, "M10-Contacts", "Modifier infos client", i, "POST",
                        f"/contacts/clients/{client_id}/edit",
                        data={
                            "name": "Client HTTP Test",
                            "phone": f"055501{i:04d}",
                            "address": f"Adresse modifiée #{i}",
                            "notes": "Modifié par stress test",
                        },
                        report=report)

            await check(client, "M10-Contacts", "Fiche état de compte client", i, "GET",
                        f"/clients/{client_id}", report=report)

            await check(client, "M10-Contacts", "Imprimer fiche client PDF", i, "GET",
                        f"/clients/{client_id}/print-history", report=report)

        if supplier_id:
            await check(client, "M10-Contacts", "Fiche fournisseur", i, "GET",
                        f"/suppliers/{supplier_id}", report=report)

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 11 — Historique & Audit
# =============================================================================
async def test_module11_history(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n🔍 MODULE 11 : Historique & Audit")
    for i in range(1, repeat + 1):
        await check(client, "M11-History", "Historique global opérations", i, "GET",
                    "/operations", report=report)
        await check(client, "M11-History", "Recherche par mot-clé", i, "GET",
                    "/operations?search=HTTP+Test", report=report)
        await check(client, "M11-History", "Filtre type achat", i, "GET",
                    "/operations?type=purchase", report=report)
        await check(client, "M11-History", "Filtre type vente", i, "GET",
                    "/operations?type=sale", report=report)
        await check(client, "M11-History", "Filtre type versement", i, "GET",
                    "/operations?type=payment", report=report)
        await check(client, "M11-History", "Filtre par date du jour", i, "GET",
                    f"/operations?date_from={date.today().isoformat()}&date_to={date.today().isoformat()}",
                    report=report)
        await check(client, "M11-History", "Journal d'audit", i, "GET",
                    "/admin/audit", report=report)
        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 12 — Import / Export
# =============================================================================
async def test_module12_import_export(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n📥 MODULE 12 : Import & Export")
    for i in range(1, repeat + 1):
        # Exports
        await check(client, "M12-Import/Export", "Export rapport CSV", i, "GET",
                    "/reports/export-csv", report=report)

        # Get API token for clients/export (which requires Bearer token)
        token = None
        try:
            r = await client.client.post("/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
            if r.status_code == 200:
                token = r.json().get("data", {}).get("access_token")
        except Exception as e:
            logger.warning(f"  ⚠️ Obtenir token API a échoué: {e}")

        if token:
            client.client.headers["Authorization"] = f"Bearer {token}"

        await check(client, "M12-Import/Export", "Export clients JSON (API)", i, "GET",
                    "/api/v1/clients/export", report=report)

        if token:
            client.client.headers.pop("Authorization", None)

        await check(client, "M12-Import/Export", "Export transactions CSV (rapport)", i, "GET",
                    "/reports?period=month", report=report)

        # Page import clients
        await check(client, "M12-Import/Export", "Page import clients Excel (GET)", i, "GET",
                    "/contacts/clients/import-excel", report=report)
        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 13 — Notes
# =============================================================================
async def test_module13_notes(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n📝 MODULE 13 : Bloc-notes")
    for i in range(1, min(repeat, 5) + 1):
        await check(client, "M13-Notes", "Consulter notes (GET)", i, "GET",
                    "/notes", report=report)

        # Créer une note
        await check(client, "M13-Notes", "Créer une note", i, "POST",
                    "/notes/api/create",
                    data={"title": f"Note Stress #{i}", "content": f"Contenu de test #{i}",
                          "color": "yellow"},
                    report=report)

        # Retrouver l'ID de la note créée et la modifier/supprimer
        try:
            from app.core.runtime_paths import paths
            import json
            note_files = sorted(paths.notes_dir.glob("note_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
            if note_files:
                note_data = json.loads(note_files[0].read_text(encoding="utf-8"))
                note_id = note_data.get("id", "")
                if note_id:
                    # L'API attend le champ 'id' (sans préfixe 'note_')
                    clean_id = note_id.replace("note_", "")
                    await check(client, "M13-Notes", "Épingler une note", i, "POST",
                                "/notes/api/save",
                                data={"id": clean_id, "title": f"Note Stress #{i}",
                                      "content": "Épinglée", "color": "green", "pinned": "1"},
                                report=report)
                    await check(client, "M13-Notes", "Supprimer une note", i, "POST",
                                "/notes/api/delete",
                                data={"id": clean_id},
                                report=report)
        except Exception as e:
            logger.warning(f"  ⚠️ Notes test exception: {e}")

        await asyncio.sleep(0.1)


# =============================================================================
# MODULE 14 — Sabrina (IA) via API REST
# =============================================================================
async def test_module14_sabrina(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n🤖 MODULE 14 : Commandes Sabrina (IA)")
    prompts = [
        "Quel est le total des ventes aujourd'hui ?",
        "Montre-moi les 5 derniers achats.",
        "Quels clients ont des dettes impayées ?",
        "Qu'est-ce que tu as retenu dans ta mémoire ?",
        "Retiens que le client HTTP Test préfère payer en espèces.",
    ]

    for i in range(1, min(repeat, 5) + 1):
        prompt = prompts[(i - 1) % len(prompts)]
        r = await client.client.post(
            "/assistant/chat",
            json={"message": prompt},
            headers={"X-CSRFToken": client._csrf_token or "", "Content-Type": "application/json"},
        )
        ok = r.status_code in (200, 202)
        result = TestResult("M14-Sabrina", f"Question Sabrina: {prompt[:40]}", i,
                           r.status_code, ok, "" if ok else r.text[:100])
        report.add(result)
        await asyncio.sleep(1.0)  # Rate limit gentil


# =============================================================================
# MODULE 15 — Administration
# =============================================================================
async def test_module15_admin(client: FABClient, report: TestReport, repeat: int):
    logger.info("\n⚙️  MODULE 15 : Administration Système")
    for i in range(1, repeat + 1):
        await check(client, "M15-Admin", "Page administration (GET)", i, "GET",
                    "/admin", report=report)

        # Créer un utilisateur temporaire
        await client.get("/admin")
        await check(client, "M15-Admin", "Créer compte utilisateur", i, "POST",
                    "/admin",
                    data={
                        "action": "create_user",
                        "username": f"testuser_{i}",
                        "password": "Test1234!",
                        "role": "operator",
                    },
                    report=report)

        # Modifier paramètres entreprise
        await client.get("/admin")
        await check(client, "M15-Admin", "Modifier infos entreprise", i, "POST",
                    "/admin",
                    data={
                        "action": "update_company",
                        "company_name": "FABouanes STRESS TEST",
                        "company_address": f"Adresse Test #{i}",
                        "company_phone": "0555000000",
                        "company_nif": "123456789",
                    },
                    report=report)

        # Backup via POST /admin avec action=backup_now
        await client.get("/admin")
        await check(client, "M15-Admin", "Créer sauvegarde", i, "POST",
                    "/admin",
                    data={"action": "backup_now"},
                    report=report)

        # Audit log
        await check(client, "M15-Admin", "Journal d'audit (admin)", i, "GET",
                    "/admin/audit", report=report)

        await asyncio.sleep(0.3)


# =============================================================================
# NETTOYAGE FINAL
# =============================================================================
async def cleanup():
    """Supprime toutes les données de test de la base de données."""
    logger.info("\n🧹 Nettoyage des données de test...")
    from app.core.db_helpers import execute_db
    deletes = [
        "DELETE FROM supplier_payments WHERE notes LIKE '%stress test%'",
        "DELETE FROM payments WHERE notes LIKE '%stress test%' OR notes LIKE '%Stress%'",
        "DELETE FROM raw_sales WHERE notes LIKE '%stress test%'",
        "DELETE FROM sales WHERE notes LIKE '%stress test%'",
        "DELETE FROM sale_documents WHERE notes LIKE '%stress test%'",
        "DELETE FROM purchases WHERE notes LIKE '%stress test%'",
        "DELETE FROM purchase_documents WHERE notes LIKE '%stress test%'",
        "DELETE FROM expenses WHERE description LIKE '%stress test%' OR description LIKE '%Stress%'",
        "DELETE FROM production_batches WHERE notes LIKE '%stress test%'",
        "DELETE FROM raw_materials WHERE name LIKE '%HTTP Test%' OR name LIKE 'Maïs Test%'",
        "DELETE FROM finished_products WHERE name LIKE '%HTTP Test%' OR name LIKE 'Aliment Bovin Test%'",
        "DELETE FROM clients WHERE name = 'Client HTTP Test'",
        "DELETE FROM suppliers WHERE name = 'Fournisseur HTTP Test'",
        "DELETE FROM users WHERE username LIKE 'testuser_%'",
    ]
    errors = []
    for sql in deletes:
        try:
            execute_db(sql)
        except Exception as e:
            errors.append(f"{sql[:50]}…: {e}")

    if errors:
        for err in errors:
            logger.warning(f"  ⚠️ Cleanup partiel: {err}")
    else:
        logger.info("  ✅ Base de données nettoyée avec succès.")

    # Nettoyage notes physiques
    try:
        from app.core.runtime_paths import paths
        import json as _json
        if paths.notes_dir.exists():
            for f in paths.notes_dir.glob("note_*.json"):
                try:
                    data = _json.loads(f.read_text(encoding="utf-8"))
                    if "Stress" in str(data.get("title", "")):
                        f.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    _state.clear()


# =============================================================================
# MAIN
# =============================================================================
async def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="FABouanes HTTP Stress Test")
    parser.add_argument("--url", default=BASE_URL, help="URL de l'application")
    parser.add_argument("--repeat", type=int, default=10, help="Répétitions par module (10-20)")
    args = parser.parse_args()

    BASE_URL = args.url
    repeat = max(5, min(20, args.repeat))

    logger.info("=" * 80)
    logger.info(f"  FABouanes HTTP Stress Test — {repeat} répétitions par module")
    logger.info(f"  Cible : {BASE_URL}")
    logger.info(f"  Identifiants : {USERNAME} / {PASSWORD}")
    logger.info("=" * 80)

    report = TestReport()

    # Vérifier que l'appli est démarrée
    try:
        async with httpx.AsyncClient(timeout=5) as probe:
            r = await probe.get(BASE_URL)
            logger.info(f"  ✅ Application accessible : {r.status_code}")
    except Exception as e:
        logger.error(f"  ❌ Application inaccessible sur {BASE_URL} : {e}")
        logger.error("  ➡️  Assurez-vous que l'application est démarrée avant de lancer ce script.")
        sys.exit(1)

    # Créer un client HTTP principal (session persistante)
    client = FABClient(BASE_URL)
    login_ok = await client.login()
    if not login_ok:
        logger.error("❌ Impossible de se connecter. Arrêt du stress test.")
        await client.close()
        sys.exit(1)

    try:
        await test_module1_auth(report, repeat)
        # Re-login après les tests d'auth (qui déconnectent)
        main_client = FABClient(BASE_URL)
        await main_client.login()

        await test_module2_dashboard(main_client, report, repeat)
        await test_module3_catalog(main_client, report, repeat)
        await test_module4_sales(main_client, report, repeat)
        await test_module5_purchases(main_client, report, repeat)
        await test_module6_payments(main_client, report, repeat)
        await test_module7_expenses(main_client, report, repeat)
        await test_module8_stocks(main_client, report, repeat)
        await test_module9_production(main_client, report, repeat)
        await test_module10_contacts(main_client, report, repeat)
        await test_module11_history(main_client, report, repeat)
        await test_module12_import_export(main_client, report, repeat)
        await test_module13_notes(main_client, report, repeat)
        await test_module14_sabrina(main_client, report, repeat)
        await test_module15_admin(main_client, report, repeat)

        await main_client.close()

    finally:
        await client.close()
        await cleanup()

    print(report.summary())

    # Sauvegarder le rapport
    report_path = Path("http_stress_report.txt")
    report_path.write_text(report.summary(), encoding="utf-8")
    logger.info(f"\n📄 Rapport sauvegardé dans : {report_path.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
