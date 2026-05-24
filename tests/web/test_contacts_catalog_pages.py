from __future__ import annotations

from tests.conftest import extract_csrf

def test_contacts_page_renders(logged_client):
    response = logged_client.get("/contacts")
    assert response.status_code == 200
    assert "Client" in response.text or "Fournisseur" in response.text
    assert 'data-font="jakarta"' in response.text
    assert 'data-font="google"' not in response.text
    assert 'data-nav-layout="vertical"' in response.text
    assert 'id="sideNavToggle"' in response.text


def test_suppliers_page_renders(logged_client):
    response = logged_client.get("/contacts?type=supplier")
    assert response.status_code == 200
    assert "Contacts" in response.text
    assert "Fournisseur" in response.text


def test_supplier_detail_page_renders(logged_client, first_supplier_id):
    response = logged_client.get(f"/contacts/suppliers/{first_supplier_id}")
    assert response.status_code == 200
    assert "Fournisseur" in response.text


def test_catalog_page_renders(logged_client):
    response = logged_client.get("/catalog")
    assert response.status_code == 200
    assert "Catalogue" in response.text or "Produits finis" in response.text or "Matieres premieres" in response.text


def test_quick_add_page_renders(logged_client):
    response = logged_client.get("/quick-add")
    assert response.status_code == 200
    assert "Ajout rapide" in response.text or "client" in response.text.lower()


def test_raw_material_edit_page_renders(logged_client, first_raw_material_id):
    response = logged_client.get(f"/raw-materials/{first_raw_material_id}/edit")
    assert response.status_code == 200
    assert "Matiere" in response.text or "Stock" in response.text


def test_product_edit_page_renders(logged_client, first_product_id):
    response = logged_client.get(f"/products/{first_product_id}/edit")
    assert response.status_code == 200
    assert "Produit" in response.text or "Stock" in response.text


def test_create_raw_material_via_form_with_validation(logged_client):
    # 1. Fetch form to extract CSRF
    page = logged_client.get("/catalog/new?kind=raw")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    # 2. Submit valid form with European currency style formats
    response = logged_client.post(
        "/catalog/new",
        data={
            "csrf_token": csrf_token,
            "kind": "raw",
            "name": "autre: Integration Raw Test",
            "unit": "kg",
            "stock_qty": "1 250,50",
            "avg_cost": "12,5",
            "sale_price": "15,0",
            "alert_threshold": "10,0"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    # 3. Verify in database
    from app.core.db_access import query_db, execute_db
    row = query_db("SELECT * FROM raw_materials WHERE name = %s", ("autre: Integration Raw Test",), one=True)
    assert row is not None
    assert float(row["stock_qty"]) == 1250.50
    assert float(row["avg_cost"]) == 12.5
    assert float(row["sale_price"]) == 15.0
    assert float(row["alert_threshold"]) == 10.0

    # Cleanup
    execute_db("DELETE FROM raw_materials WHERE id = %s", (row["id"],))


def test_create_finished_product_via_form_with_validation(logged_client):
    # 1. Fetch form to extract CSRF
    page = logged_client.get("/catalog/new?kind=finished")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    # 2. Submit valid form with European currency style formats and select named 'unit'
    response = logged_client.post(
        "/catalog/new",
        data={
            "csrf_token": csrf_token,
            "kind": "finished",
            "name": "autre: Integration Product Test",
            "unit": "Sac",  # The select input name is 'unit' in the template
            "stock_qty": "2 500,75",
            "avg_cost": "20,0",
            "sale_price": "30,25"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    # 3. Verify in database
    from app.core.db_access import query_db, execute_db
    row = query_db("SELECT * FROM finished_products WHERE name = %s", ("autre: Integration Product Test",), one=True)
    assert row is not None
    assert row["default_unit"] == "Sac"
    assert float(row["stock_qty"]) == 2500.75
    assert float(row["avg_cost"]) == 20.0
    assert float(row["sale_price"]) == 30.25

    # Cleanup
    execute_db("DELETE FROM finished_products WHERE id = %s", (row["id"],))


def test_edit_raw_material_submits_with_european_format(logged_client, first_raw_material_id):
    page = logged_client.get(f"/raw-materials/{first_raw_material_id}/edit")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    response = logged_client.post(
        f"/raw-materials/{first_raw_material_id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "Matiere Test Custom",
            "unit": "kg",
            "stock_qty": "150,75",
            "avg_cost": "55,25",
            "sale_price": "70,5",
            "alert_threshold": "12,0"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    from app.core.db_access import query_db
    row = query_db("SELECT * FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    assert row is not None
    assert row["name"] == "autre: Matiere Test Custom"
    assert float(row["stock_qty"]) == 150.75
    assert float(row["avg_cost"]) == 55.25
    assert float(row["sale_price"]) == 70.5
    assert float(row["alert_threshold"]) == 12.0


def test_edit_product_submits_with_european_format(logged_client, first_product_id):
    page = logged_client.get(f"/products/{first_product_id}/edit")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    response = logged_client.post(
        f"/products/{first_product_id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "Produit Test Custom",
            "default_unit": "Sac",
            "stock_qty": "95,5",
            "avg_cost": "95,25",
            "sale_price": "125,5"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    from app.core.db_access import query_db
    row = query_db("SELECT * FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    assert row is not None
    assert row["name"] == "autre: Produit Test Custom"
    assert row["default_unit"] == "Sac"
    assert float(row["stock_qty"]) == 95.5
    assert float(row["avg_cost"]) == 95.25
    assert float(row["sale_price"]) == 125.5

