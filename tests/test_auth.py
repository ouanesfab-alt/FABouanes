import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_page():
    response = client.get("/login")
    assert response.status_code == 200
    assert "Connexion" in response.text

def test_login_invalid_credentials():
    # First GET to obtain the session and CSRF token
    get_res = client.get("/login")
    from tests.conftest import extract_csrf
    csrf_token = extract_csrf(get_res.text)
    
    response = client.post("/login", data={
        "username": "wrong", 
        "password": "wrong",
        "csrf_token": csrf_token
    })
    # Status code is 200 because it re-renders the login page with an error flash message
    assert response.status_code == 200
    assert "incorrect" in response.text.lower()



def test_api_login_invalid_credentials():
    response = client.post("/api/v1/auth/login", json={"username": "wrong", "password": "wrong"})
    assert response.status_code == 401
    assert "error" in response.json()

@pytest.mark.skip(reason="Requires valid admin credentials setup in test DB")
def test_api_login_success():
    # This would require a pre-seeded test database with a known user
    pass
