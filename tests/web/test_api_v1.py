from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db_access import query_db, execute_db



# ================= AUTH ENDPOINTS =================

def test_api_login_success(client: TestClient):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "1234"})
    assert response.status_code == 200
    res = response.json()
    assert "access_token" in res["data"]
    assert "refresh_token" in res["data"]
    assert res["data"]["user"]["username"] == "admin"

def test_api_login_validation_errors(client: TestClient):
    # Empty username
    response = client.post("/api/v1/auth/login", json={"username": "", "password": "1234"})
    assert response.status_code == 422
    
    # Empty password
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": ""})
    assert response.status_code == 422

def test_api_auth_refresh(client: TestClient, api_tokens):
    _, refresh_token = api_tokens
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    res = response.json()
    assert "access_token" in res["data"]

def test_api_auth_refresh_invalid(client: TestClient):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid_refresh_token"})
    assert response.status_code == 401

def test_api_auth_me(client: TestClient, api_headers):
    response = client.get("/api/v1/auth/me", headers=api_headers)
    assert response.status_code == 200
    res = response.json()
    assert res["data"]["username"] == "admin"

def test_api_auth_logout(client: TestClient, api_headers, api_tokens):
    _, refresh_token = api_tokens
    response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token}, headers=api_headers)
    assert response.status_code == 200
    assert response.json()["data"]["revoked"] is True

# ================= ADMIN ENDPOINTS =================

def test_api_audit_logs(client: TestClient, api_headers):
    # Insert a dummy audit log first to guarantee we have one
    execute_db("INSERT INTO audit_logs (actor_username, actor_role, action, source) VALUES (%s, %s, %s, %s)",
               ("admin", "admin", "test_event", "test"))
    
    response = client.get("/api/v1/audit-logs", headers=api_headers)
    assert response.status_code == 200
    res = response.json()
    assert len(res["data"]) > 0

# ================= PAYMENTS ENDPOINTS =================

def test_api_payments_crud(client: TestClient, api_headers, first_client_id, first_product_id):
    # Insert a dummy credit sale to give the client outstanding debt so a versement payment can be recorded
    execute_db("""
        INSERT INTO sales (client_id, document_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (first_client_id, None, first_product_id, 1.0, "kg", 500.00, 500.00, "credit", 0.00, 500.00, 300.00, 200.00, "2026-05-19", "api test sale"))

    # 1. List payments
    response = client.get("/api/v1/payments", headers=api_headers)
    assert response.status_code == 200
    
    # 2. Create a payment
    payload = {
        "client_id": first_client_id,
        "amount": 250.50,
        "notes": "API test payment"
    }
    response = client.post("/api/v1/payments", json=payload, headers=api_headers)
    assert response.status_code == 201
    res = response.json()
    assert res["data"]["payment_type"] == "versement"
    payment_id = res["data"]["payment"]["id"]
    
    # 3. Retrieve payment detail
    response = client.get(f"/api/v1/payments/{payment_id}", headers=api_headers)
    assert response.status_code == 200
    assert response.json()["data"]["notes"] == "API test payment"
    
    # 4. Update the payment
    update_payload = {
        "client_id": first_client_id,
        "amount": "300.00",  # String number handles conversions too
        "notes": "Updated API payment"
    }
    response = client.put(f"/api/v1/payments/{payment_id}", json=update_payload, headers=api_headers)
    assert response.status_code == 200
    payment_id = response.json()["data"]["id"]
    
    # 5. Delete the payment
    response = client.delete(f"/api/v1/payments/{payment_id}", headers=api_headers)
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

def test_api_payment_validation_errors(client: TestClient, api_headers, first_client_id):
    # Invalid amount
    payload = {"client_id": first_client_id, "amount": "invalid_amount"}
    response = client.post("/api/v1/payments", json=payload, headers=api_headers)
    assert response.status_code == 422
    
    # Missing/invalid client
    payload = {"client_id": "", "amount": 100}
    response = client.post("/api/v1/payments", json=payload, headers=api_headers)
    assert response.status_code == 422

def test_api_payment_not_found(client: TestClient, api_headers):
    response = client.get("/api/v1/payments/999999", headers=api_headers)
    assert response.status_code == 404
    
    response = client.put("/api/v1/payments/999999", json={"client_id": 1, "amount": 100}, headers=api_headers)
    assert response.status_code == 404
    
    response = client.delete("/api/v1/payments/999999", headers=api_headers)
    assert response.status_code == 404

# ================= PRODUCTION ENDPOINTS =================

def test_api_production_crud(client: TestClient, api_headers, first_product_id, first_raw_material_id):
    # 1. Reset stocks to ensure valid production run is possible
    execute_db("UPDATE raw_materials SET stock_qty = 1000.00, avg_cost = 50.00 WHERE id = %s", (first_raw_material_id,))
    
    # 2. Get production batches
    response = client.get("/api/v1/production-batches", headers=api_headers)
    assert response.status_code == 200
    
    # 3. Create a production batch (with new recipe save)
    payload = {
        "finished_product_id": first_product_id,
        "output_quantity": 10.0,
        "raw_material_id[]": [first_raw_material_id],
        "quantity[]": [20.0],
        "save_recipe": 1,
        "recipe_name": "API New Test Recipe"
    }
    response = client.post("/api/v1/production-batches", json=payload, headers=api_headers)
    assert response.status_code == 201
    res = response.json()
    batch_id = res["data"]["batch"]["id"]
    recipe_id = res["data"]["recipe_id"]
    
    # 4. Get batch detail
    response = client.get(f"/api/v1/production-batches/{batch_id}", headers=api_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) == 1
    
    # 5. List recipes
    response = client.get("/api/v1/recipes", headers=api_headers)
    assert response.status_code == 200
    
    # 6. Get recipe detail
    response = client.get(f"/api/v1/recipes/{recipe_id}", headers=api_headers)
    assert response.status_code == 200
    
    # 7. Delete production batch (reverses stock)
    response = client.delete(f"/api/v1/production-batches/{batch_id}", headers=api_headers)
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

def test_api_production_validation_errors(client: TestClient, api_headers, first_product_id, first_raw_material_id):
    # Output quantity <= 0
    payload = {
        "finished_product_id": first_product_id,
        "output_quantity": 0.0,
        "raw_material_id[]": [first_raw_material_id],
        "quantity[]": [20.0]
    }
    response = client.post("/api/v1/production-batches", json=payload, headers=api_headers)
    assert response.status_code == 422 or response.status_code == 400

    # Excessive raw material quantity (exceeds stock)
    execute_db("UPDATE raw_materials SET stock_qty = 5.00 WHERE id = %s", (first_raw_material_id,))
    payload = {
        "finished_product_id": first_product_id,
        "output_quantity": 10.0,
        "raw_material_id[]": [first_raw_material_id],
        "quantity[]": [50.0]
    }
    response = client.post("/api/v1/production-batches", json=payload, headers=api_headers)
    assert response.status_code == 400 or response.status_code == 422 or response.status_code == 500

def test_api_production_not_found(client: TestClient, api_headers):
    response = client.get("/api/v1/production-batches/999999", headers=api_headers)
    assert response.status_code == 404
    
    response = client.delete("/api/v1/production-batches/999999", headers=api_headers)
    assert response.status_code == 404
    
    response = client.get("/api/v1/recipes/999999", headers=api_headers)
    assert response.status_code == 404
