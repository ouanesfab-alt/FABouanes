from __future__ import annotations


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
