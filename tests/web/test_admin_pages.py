from __future__ import annotations

from werkzeug.security import check_password_hash

from app.core.db_access import query_db
from tests.conftest import extract_csrf


def test_admin_panel_renders(logged_client):
    response = logged_client.get("/admin")
    assert response.status_code == 200
    assert "Parametres" in response.text
    assert "Etat du systeme" in response.text
    assert "Nouveau PIN" in response.text


def test_admin_can_update_user_password(logged_client):
    page = logged_client.get("/admin")
    csrf_token = extract_csrf(page.text)
    user = query_db("SELECT id FROM users WHERE username = %s", ("admin",), one=True)
    assert user is not None

    response = logged_client.post(
        "/admin",
        data={
            "csrf_token": csrf_token,
            "action": "update_user",
            "user_id": str(user["id"]),
            "role": "admin",
            "is_active": "1",
            "new_password": "9876",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    updated = query_db("SELECT password_hash, role, is_active FROM users WHERE id = %s", (user["id"],), one=True)
    assert updated is not None
    assert check_password_hash(updated["password_hash"], "9876")
    assert updated["role"] == "admin"
    assert int(updated["is_active"]) == 1


def test_admin_system_status_renders(logged_client):
    response = logged_client.get("/admin/system-status")
    assert response.status_code == 200
    assert "Diagnostic systeme" in response.text


def test_admin_system_status_export(logged_client):
    response = logged_client.get("/admin/system-status/export")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "database" in response.json()
