#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/test_error_handling.py
Vérification des gestionnaires d'erreurs (Exception Handlers) de FABouanes.
Teste que les requêtes API reçoivent du JSON et les requêtes Web reçoivent une page HTML explicative.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le chemin racine du projet à PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import Request
from fastapi.testclient import TestClient
from app.main import app
from app.core.exceptions import NotFoundError, ValidationError, ConflictError

# ── Définition de routes temporaires de test ──

@app.get("/test-err-notfound")
def route_notfound():
    raise NotFoundError("Client", 999)

@app.get("/test-err-val")
def route_val():
    raise ValidationError("Le nom du client est obligatoire.", field="name")

@app.get("/test-err-conflict")
def route_conflict():
    raise ConflictError("Impossible de valider car le stock est insuffisant.")

@app.get("/test-err-foreignkey")
def route_foreignkey():
    raise Exception("violates foreign key constraint 'sales_client_id_fkey' on table 'sales'")

@app.get("/test-err-unique")
def route_unique():
    raise Exception("duplicate key value violates unique constraint 'clients_name_key'")

@app.get("/test-err-overflow")
def route_overflow():
    raise Exception("numeric value out of range")


# ── Lancement des tests ──

client = TestClient(app, raise_server_exceptions=False)

print("=" * 80)
print("🧪 TESTING FABOUANES PREMIUM EXPLANATORY ERROR HANDLERS")
print("=" * 80)

# 1. Test de NotFoundError
print("\n🔹 Test 1 : NotFoundError")
# Version API (JSON)
res_json = client.get("/test-err-notfound", headers={"Accept": "application/json"})
assert res_json.status_code == 404
assert res_json.json()["success"] is False
assert "introuvable" in res_json.json()["error"]["message"]
print("   ✅ API (JSON) : Reçu 404 avec message explicatif.")

# Version Web (HTML)
res_html = client.get("/test-err-notfound", headers={"Accept": "text/html"})
print(f"DEBUG status_code = {res_html.status_code}")
print(f"DEBUG text[:300] = {res_html.text[:300]}")
assert res_html.status_code == 404
assert "Page introuvable" in res_html.text
assert "techniques" in res_html.text.lower()
print("   ✅ Web (HTML) : Reçu page d'erreur 404 premium HTML.")

# 2. Test de ValidationError
print("\n🔹 Test 2 : ValidationError")
# Version API (JSON)
res_json = client.get("/test-err-val", headers={"Accept": "application/json"})
assert res_json.status_code == 422
assert res_json.json()["error"]["code"] == "validation_error"
print("   ✅ API (JSON) : Reçu 422 ValidationError.")

# Version Web (HTML)
res_html = client.get("/test-err-val", headers={"Accept": "text/html"})
assert res_html.status_code == 422
assert "invalides" in res_html.text
print("   ✅ Web (HTML) : Reçu page d'erreur 422 premium HTML.")

# 3. Test de ConflictError
print("\n🔹 Test 3 : ConflictError")
# Version API (JSON)
res_json = client.get("/test-err-conflict", headers={"Accept": "application/json"})
assert res_json.status_code == 409
assert res_json.json()["error"]["code"] == "conflict"
print("   ✅ API (JSON) : Reçu 409 ConflictError.")

# Version Web (HTML)
res_html = client.get("/test-err-conflict", headers={"Accept": "text/html"})
assert res_html.status_code == 409
assert "Conflit" in res_html.text
print("   ✅ Web (HTML) : Reçu page d'erreur 409 premium HTML.")

# 4. Test de ForeignKeyViolation (Simulée)
print("\n🔹 Test 4 : ForeignKeyViolation (Simulée)")
# Version API (JSON)
res_json = client.get("/test-err-foreignkey", headers={"Accept": "application/json"})
assert res_json.status_code == 500
assert "operation" in res_json.json()["error"]["message"].lower() or "opération" in res_json.json()["error"]["message"].lower()
print("   ✅ API (JSON) : Reçu 500 avec explication de contrainte de clé étrangère.")

# Version Web (HTML)
res_html = client.get("/test-err-foreignkey", headers={"Accept": "text/html"})
assert res_html.status_code == 500
assert "Impossible" in res_html.text or "impossible" in res_html.text
print("   ✅ Web (HTML) : Reçu page d'erreur 500 premium HTML avec explication de clé étrangère.")

# 5. Test de UniqueViolation (Simulée)
print("\n🔹 Test 5 : UniqueViolation (Simulée)")
# Version API (JSON)
res_json = client.get("/test-err-unique", headers={"Accept": "application/json"})
assert res_json.status_code == 500
assert "existe" in res_json.json()["error"]["message"]
print("   ✅ API (JSON) : Reçu 500 avec explication d'unicité.")

# Version Web (HTML)
res_html = client.get("/test-err-unique", headers={"Accept": "text/html"})
assert res_html.status_code == 500
assert "existe" in res_html.text
print("   ✅ Web (HTML) : Reçu page d'erreur 500 premium HTML avec explication d'unicité.")

# 6. Test de NumericValueOutOfRange (Simulée)
print("\n🔹 Test 6 : NumericValueOutOfRange (Simulée)")
# Version API (JSON)
res_json = client.get("/test-err-overflow", headers={"Accept": "application/json"})
assert res_json.status_code == 500
assert "limites" in res_json.json()["error"]["message"]
print("   ✅ API (JSON) : Reçu 500 avec explication de débordement de capacité.")

# Version Web (HTML)
res_html = client.get("/test-err-overflow", headers={"Accept": "text/html"})
assert res_html.status_code == 500
assert "limites" in res_html.text
print("   ✅ Web (HTML) : Reçu page d'erreur 500 premium HTML avec explication de débordement.")

print("\n" + "=" * 80)
print("🏆 TOUS LES GESTIONNAIRES D'ERREURS DÉTAILLÉES PASSENT AVEC SUCCÈS À 100% !")
print("=" * 80)
