from __future__ import annotations


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Connexion" in response.text
    assert "dashboard.webp" in response.text



def test_login_redirects_after_success(client):
    response = client.get("/login")
    from tests.conftest import extract_csrf

    csrf_token = extract_csrf(response.text)
    post = client.post(
        "/login",
        data={"username": "admin", "password": "1234", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert post.status_code == 303
    assert post.headers["location"] in {"/", "/change-password"}
