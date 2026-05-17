from __future__ import annotations


def test_clients_page_renders(logged_client):
    response = logged_client.get("/contacts?type=client")
    assert response.status_code == 200
    assert "Contacts" in response.text
    assert "Client" in response.text
