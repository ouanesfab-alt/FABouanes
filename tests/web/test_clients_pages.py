from __future__ import annotations

from app.repositories.client_repository import get_client, find_client_by_name
from app.core.db_access import execute_db
from tests.conftest import extract_csrf


def test_clients_page_renders(logged_client):
    response = logged_client.get("/contacts?type=client")
    assert response.status_code == 200
    assert "Contacts" in response.text
    assert "Client" in response.text


def test_new_client_form_renders(logged_client):
    response = logged_client.get("/contacts/clients/new")
    assert response.status_code == 200
    assert "Ajouter un client" in response.text


def test_create_client_via_form_with_validation(logged_client):
    # 1. Fetch form to extract CSRF
    page = logged_client.get("/contacts/clients/new")
    csrf_token = extract_csrf(page.text)

    # 2. Submit valid form with European currency style format in opening credit
    response = logged_client.post(
        "/contacts/clients/new",
        data={
            "csrf_token": csrf_token,
            "name": "Integration Client Test",
            "phone": "0555123456",
            "address": "123 Test Street",
            "opening_credit": "1 500,50",  # Test European decimal format parsing
            "notes": "Testing Pydantic validation"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    # 3. Verify in database
    client = find_client_by_name("Integration Client Test")
    assert client is not None
    
    client_detail = get_client(client["id"])
    assert client_detail["phone"] == "0555123456"
    assert float(client_detail["opening_credit"]) == 1500.50

    # Cleanup
    execute_db("DELETE FROM clients WHERE id = %s", (client["id"],))


def test_create_client_validation_error(logged_client):
    page = logged_client.get("/contacts/clients/new")
    csrf_token = extract_csrf(page.text)

    # Submit an invalid negative opening credit
    response = logged_client.post(
        "/contacts/clients/new",
        data={
            "csrf_token": csrf_token,
            "name": "Integration Invalid Client",
            "phone": "0555123456",
            "address": "123 Test Street",
            "opening_credit": "-100",  # Invalid negative
            "notes": "Testing Pydantic validation failure"
        },
        follow_redirects=False
    )
    assert response.status_code == 200  # Stays on template
    assert "Erreur de validation" in response.text
    assert "negative" in response.text or "négatif" in response.text


def test_edit_client_renders_and_submits(logged_client):
    # 1. Insert direct dummy client
    execute_db(
        "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
        ("Dummy Client", "0550112233", "Old Road", "Old notes", 0.0)
    )
    client = find_client_by_name("Dummy Client")
    client_id = client["id"]

    # 2. Open edit page
    page = logged_client.get(f"/contacts/clients/{client_id}/edit")
    assert page.status_code == 200
    csrf_token = extract_csrf(page.text)

    # 3. Submit valid updates
    response = logged_client.post(
        f"/contacts/clients/{client_id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "Dummy Client - Edited",
            "phone": "0550999999",
            "address": "New Road",
            "opening_credit": "450.75",
            "notes": "New notes"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    # 4. Verify updates
    updated = get_client(client_id)
    assert updated["name"] == "Dummy Client - Edited"
    assert updated["phone"] == "0550999999"
    assert float(updated["opening_credit"]) == 450.75

    # Cleanup
    execute_db("DELETE FROM clients WHERE id = %s", (client_id,))
