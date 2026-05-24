#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/test_catalog.py
Test fonctionnel du catalogue de FABouanes (Matières premières et Produits finis).
Vérifie la création par sélecteur de catégorie prédéfinie et par champ personnalisé.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le chemin racine du projet à PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import app.web.deps as web_deps

# Bypasser CSRF et authentification BEFORE importing app routes
web_deps.get_current_user = lambda request: {"id": 1, "username": "admin", "role": "admin", "is_active": 1}
web_deps.require_permission = lambda request, permission: None

async def mock_csrf(request):
    return None
web_deps.csrf_protect = mock_csrf

try:
    import app.modules.catalog.web as catalog_web
    catalog_web.require_permission = lambda request, permission: None
    catalog_web.csrf_protect = mock_csrf
except ImportError:
    pass

try:
    import app.web.catalog_pages as catalog_pages
    catalog_pages.require_permission = lambda request, permission: None
    catalog_pages.csrf_protect = mock_csrf
except ImportError:
    pass

from app.main import app
from fastapi.testclient import TestClient
from app.core.db_access import query_db

def main():
    # Nettoyage pour éviter les conflits d'unicité
    from app.core.db_access import execute_db
    execute_db("DELETE FROM finished_products WHERE name IN ('Aliment Démarrage', 'Aliment Ultra-Croissance Bio', 'autre: Aliment Ultra-Croissance Bio', 'autre: Aliment Ultra-Croissance Bio Premium')")
    execute_db("DELETE FROM raw_materials WHERE name IN ('Maïs', 'autre: Aliment Ultra-Croissance Bio', 'autre: Aliment Ultra-Croissance Bio Premium')")

    client = TestClient(app, raise_server_exceptions=True)

    def make_request(method, url, **kwargs):
        res = getattr(client, method)(url, **kwargs)
        from app.core.async_db import async_engine
        import asyncio
        try:
            asyncio.run(async_engine.dispose())
        except Exception:
            pass
        return res

    print("=" * 80)
    print("[TEST] TESTING FABOUANES PREMIUM CATALOG SYSTEM (CREATE & EDIT)")
    print("=" * 80)

    # ── 1. Chargement de la page de création d'un produit fini ──
    print("\n* Test 1 : Chargement de la page de création (kind = finished)")
    res = make_request("get", "/catalog/new?kind=finished", headers={"Accept": "text/html"})
    print(f"DEBUG status_code = {res.status_code}")
    print(f"DEBUG text[:1000] = {res.text[:1000]}")
    assert res.status_code == 200
    # S'assurer que les presets premium sont présents dans le code HTML retourné
    print(f"DEBUG status_code = {res.status_code}")
    print(f"DEBUG text[:500] = {res.text[:500]}")
    assert "Aliment" in res.text
    assert "Croissance" in res.text or "Démarrage" in res.text
    print("   ✅ Succès : Les options prédéfinies premium s'affichent correctement.")

    # ── 2. Création d'un produit fini via PRESET ──
    print("\n* Test 2 : Création d'un produit fini avec nom prédéfini (Preset)")
    form_preset = {
        "kind": "finished",
        "name": "Aliment Démarrage",
        "unit": "kg",
        "stock_qty": "100.0",
        "avg_cost": "75.0",
        "sale_price": "95.0"
    }
    # Nous bypassons la protection CSRF dans le TestClient en omettant le jeton ou en utilisant les cookies
    res = make_request("post", "/catalog/new", data=form_preset, follow_redirects=False)
    # Si redirection vers /catalog (303), c'est une création réussie
    assert res.status_code == 303 or res.status_code == 200
    print("   - Succès : Produit créé avec nom prédéfini.")

    # ── 3. Création d'un produit fini via AUTRE / CUSTOM NAME ──
    print("\n* Test 3 : Création d'un produit fini avec nom personnalisé (Custom)")
    form_custom = {
        "kind": "finished",
        "name": "Aliment Ultra-Croissance Bio",
        "unit": "sac",
        "stock_qty": "50.0",
        "avg_cost": "120.0",
        "sale_price": "160.0"
    }
    res = make_request("post", "/catalog/new", data=form_custom, follow_redirects=False)
    print(f"DEBUG Test 3 status code: {res.status_code}")
    assert res.status_code == 303 or res.status_code == 200
    print("   - Succès : Produit créé avec nom personnalisé.")

    # ── 4. Vérification dans la base de données ──
    print("\n* Test 4 : Audit de la base de données")
    products = query_db("SELECT * FROM finished_products WHERE name = %s", ("autre: Aliment Ultra-Croissance Bio",))
    assert len(products) > 0
    p = products[0]
    print(f"   - Produit trouvé en BDD : ID={p['id']}, Nom='{p['name']}', Prix de vente={p['sale_price']} DA")

    # ── 5. Test de modification du produit (Edition) ──
    print("\n* Test 5 : Modification du produit final (Edition)")
    product_id = p["id"]
    # Charger la page d'édition
    res_edit_page = make_request("get", f"/products/{product_id}/edit", headers={"Accept": "text/html"})
    assert res_edit_page.status_code == 200
    assert "Aliment Ultra-Croissance Bio" in res_edit_page.text

    # Soumettre les modifications
    form_edit = {
        "name": "Aliment Ultra-Croissance Bio Premium",
        "default_unit": "kg",
        "stock_qty": "60.0",
        "sale_price": "180.0",
        "avg_cost": "130.0"
    }
    res_edit_post = make_request("post", f"/products/{product_id}/edit", data=form_edit, follow_redirects=False)
    assert res_edit_post.status_code == 303 or res_edit_post.status_code == 200

    # Vérifier la modification en BDD
    p_updated = query_db("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)
    assert p_updated["name"] == "autre: Aliment Ultra-Croissance Bio Premium"
    assert float(p_updated["sale_price"]) == 180.0

    print("\n" + "=" * 80)
    print("SUCCESS: ALL CATALOG TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    main()
