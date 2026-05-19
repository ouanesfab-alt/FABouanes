from __future__ import annotations

import concurrent.futures
import time

def test_volume_operations(client, api_headers):
    # Insert 1 client, 1 supplier, 1 raw material, 1 finished product
    res = client.post(
        "/api/v1/clients/",
        json={"name": "Client Volume", "phone": "000", "address": "Test"},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    client_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/suppliers/",
        json={"name": "Fournisseur Volume", "phone": "111", "address": "Test"},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    supplier_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/raw-materials",
        json={"name": "Mat Premiere", "unit": "kg", "initial_stock": 0},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    raw_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "amount_paid": 0,
            "payment_type": "credit",
            "document_date": "2026-05-19",
            "raw_material_id[]": [raw_id] * 100,
            "quantity[]": [10.0] * 100,
            "unit[]": ["kg"] * 100,
            "unit_price[]": [50.0] * 100
        },
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    
    # Check if stock is now 1000
    res = client.get("/api/v1/raw-materials", headers=api_headers)
    mats = res.json()["data"]
    mat = next(m for m in mats if m["id"] == raw_id)
    assert mat["stock_qty"] == 1000.0

    # Test Dashboard performance after insertion
    start_time = time.time()
    res = client.get("/api/v1/dashboard/", headers=api_headers)
    assert res.status_code == 200
    assert time.time() - start_time < 2.0  # Should be fast

def test_concurrency_stock_deduction(client, api_headers):
    res = client.post(
        "/api/v1/clients/",
        json={"name": "Concurrent Client"},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    client_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/raw-materials",
        json={"name": "Concurrent Material", "unit": "kg", "initial_stock": 100.0},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    raw_id = res.json()["data"]["id"]

    def sell():
        return client.post(
            "/api/v1/sales",
            json={
                "client_id": client_id,
                "amount_paid": 0,
                "payment_type": "credit",
                "document_date": "2026-05-19",
                "item_key[]": [f"raw:{raw_id}"],
                "quantity[]": [20.0],
                "unit[]": ["kg"],
                "unit_price[]": [100.0]
            },
            headers=api_headers
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(sell) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    for r in results:
        assert r.status_code in (200, 201), r.json()

    res = client.get(f"/api/v1/raw-materials", headers=api_headers)
    mats = res.json()["data"]
    mat = next(m for m in mats if m["id"] == raw_id)
    # Since 10 * 20 = 200, and initial was 100, stock should be exactly -100.0
    assert mat["stock_qty"] == -100.0

def test_math_edge_cases(client, api_headers):
    res = client.post(
        "/api/v1/clients/",
        json={"name": "Math Edge Case Client"},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    client_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/raw-materials",
        json={"name": "Math Material", "unit": "kg", "initial_stock": 50.0},
        headers=api_headers
    )
    assert res.status_code in (200, 201)
    raw_id = res.json()["data"]["id"]

    res = client.post(
        "/api/v1/sales",
        json={
            "client_id": client_id,
            "amount_paid": 2000.0,  # Paying 2000
            "payment_type": "cash",
            "document_date": "2026-05-19",
            "item_key[]": [f"raw:{raw_id}"],
            "quantity[]": [10.0],
            "unit[]": ["kg"],
            "unit_price[]": [100.0]
        },
        headers=api_headers
    )
    assert res.status_code in (200, 201)

    res = client.get(f"/api/v1/clients/{client_id}", headers=api_headers)
    client_data = res.json()["data"]
    # Debt should be negative or handled as advance?
    # Total bought: 1000, Total paid: 2000. Debt = 1000 - 2000 = -1000
    assert client_data["balance"] == -1000.0
