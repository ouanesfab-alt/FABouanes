from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.core.db_access import execute_db


@pytest.mark.asyncio
async def test_alerts_api_endpoints(client: TestClient, api_headers):
    # 1. Clean alerts and products
    execute_db("DELETE FROM stock_alerts")
    execute_db("DELETE FROM raw_materials WHERE name = %s", ("API Alert RM",))
    
    # 2. Insert raw material below threshold
    execute_db(
        "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
        ("API Alert RM", "kg", 2.0, 10.0, 15.0, 5.0)
    )
    
    # Run alert checks
    from app.services.alert_service import check_stock_alerts
    await check_stock_alerts()
    
    # 3. Retrieve alerts via API
    response = client.get("/api/v1/alerts", headers=api_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    alert = data[0]
    assert alert["product_name"] == "API Alert RM"
    alert_id = alert["id"]
    
    # 4. Acknowledge alert via API
    ack_response = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=api_headers)
    assert ack_response.status_code == 200
    assert ack_response.json()["data"]["acknowledged"] is True
    
    # 5. Retrieve alerts again - should be empty because it is acknowledged
    response2 = client.get("/api/v1/alerts", headers=api_headers)
    assert response2.status_code == 200
    assert len(response2.json()["data"]) == 0
    
    # 6. Test 404 for acknowledging non-existent alert
    error_response = client.post("/api/v1/alerts/999999/acknowledge", headers=api_headers)
    assert error_response.status_code == 404
    
    # Clean up
    execute_db("DELETE FROM stock_alerts")
    execute_db("DELETE FROM raw_materials WHERE name = %s", ("API Alert RM",))
