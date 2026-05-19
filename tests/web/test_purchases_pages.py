from __future__ import annotations

from app.core.db_access import query_db, execute_db
from tests.conftest import extract_csrf

def test_purchases_page_renders(logged_client):
    response = logged_client.get("/operations?type=purchase")
    assert response.status_code == 200
    assert "Operations" in response.text
    assert "Achats" in response.text

def test_purchase_form_renders(logged_client):
    response = logged_client.get("/operations/new?mode=achat")
    assert response.status_code == 200
    assert "Lignes d'achat" in response.text or "Ajouter une ligne" in response.text

def test_create_purchase_success(logged_client):
    # 1. Fetch form to get CSRF token
    page = logged_client.get("/operations/new?mode=achat")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    # Ensure we have a raw material
    material = query_db("SELECT id, name FROM raw_materials LIMIT 1", one=True)
    if not material:
        # Create a dummy raw material if none exists
        execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES (%s, %s, %s, %s, %s)", ("Test Material", "kg", 0, 0, 0))
        material = query_db("SELECT id, name FROM raw_materials LIMIT 1", one=True)
    
    # Ensure we have a supplier
    supplier = query_db("SELECT id FROM suppliers LIMIT 1", one=True)
    if not supplier:
        # Create a dummy supplier if none exists
        execute_db("INSERT INTO suppliers (name, phone, email, address, opening_balance) VALUES (%s, %s, %s, %s, %s)", ("Test Supplier", "123456", "test@supplier.com", "Addr", 0.0))
        supplier = query_db("SELECT id FROM suppliers LIMIT 1", one=True)

    material_id = f"raw:{material['id']}"
    supplier_id = str(supplier['id'])

    # Perform purchase creation POST request
    form_data = {
        "csrf_token": csrf_token,
        "supplier_id": supplier_id,
        "purchase_date": "2026-05-19",
        "notes": "Test purchase notes",
        "raw_material_id[]": [material_id],
        "quantity[]": ["10.0"],
        "unit[]": ["kg"],
        "unit_price[]": ["150.0"],
        "custom_item_name[]": [""]
    }

    response = logged_client.post("/operations/purchases/new", data=form_data, follow_redirects=False)
    
    # Assert successful redirect back to the operations list
    assert response.status_code == 303
    assert "/operations?type=purchase" in response.headers.get("location", "")
