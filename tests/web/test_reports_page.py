from fastapi.testclient import TestClient

def test_reports_page_renders(logged_client: TestClient):
    response = logged_client.get("/reports")
    print(f"DEBUG status = {response.status_code}")
    print(f"DEBUG body = {response.text[:2000]}")
    assert response.status_code == 200
    assert "Rapports" in response.text
