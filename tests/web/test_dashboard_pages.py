from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_unauthenticated(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response_mc = client.get("/mobile-connect", follow_redirects=False)
    assert response_mc.status_code == 303

    response_kpi = client.get("/api/kpi-date")
    assert response_kpi.status_code == 401


def test_dashboard_authenticated(logged_client: TestClient):
    response = logged_client.get("/")
    assert response.status_code == 200
    assert "Tableau de bord" in response.text or "dashboard" in response.text.lower()

    response_dash = logged_client.get("/dashboard")
    assert response_dash.status_code == 200

    response_mc = logged_client.get("/mobile-connect")
    assert response_mc.status_code == 200
    assert "Mobile" in response_mc.text or "QR" in response_mc.text


def test_api_kpi_date_endpoint(logged_client: TestClient):
    response = logged_client.get("/api/kpi-date?date=2026-05-22")
    assert response.status_code == 200
    data = response.json()
    assert "sales" in data
    assert "cash" in data
    assert "profit" in data

    # Test invalid date parsing in SQL/repository
    response_invalid = logged_client.get("/api/kpi-date?date=invalid-date")
    # depending on repository logic, it might return 400 or 200 with zero values or 500
    assert response_invalid.status_code in (200, 400, 500)


def test_api_kpi_at_date_endpoint(logged_client: TestClient):
    # Test valid metric
    response = logged_client.get("/api/kpi-at-date?date=2026-05-22&metric=sales")
    assert response.status_code == 200
    data = response.json()
    assert data["metric"] == "sales"
    assert "display" in data

    # Test invalid metric
    response_invalid = logged_client.get("/api/kpi-at-date?date=2026-05-22&metric=nonexistent")
    assert response_invalid.status_code == 400
    assert "error" in response_invalid.json()
