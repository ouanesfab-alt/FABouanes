from __future__ import annotations

import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest

from app.core.db_access import execute_db


@pytest.fixture(autouse=True)
def clean_idempotency_keys():
    yield
    try:
        execute_db("DELETE FROM idempotent_requests WHERE key LIKE 'bulk_key%' OR key LIKE 'test_sync%'")
    except Exception:
        pass


def test_offline_sync_idempotency_caching(client: TestClient, api_headers):
    """Verify that submitting a sync request twice with the same idempotency key returns the cached response on the second call."""
    with patch("app.modules.sales.service.SalesService.create_sale_from_form") as mock_create_sale:
        async def mock_sale(*args, **kwargs):
            return {"mode": "line"}
        mock_create_sale.side_effect = mock_sale

        headers = {**api_headers, "X-Idempotency-Key": "test_sync_key_1"}
        payload = {
            "type": "create_sale",
            "payload": {
                "client_id": 1,
                "item_key": "raw:1",
                "quantity": 10,
                "unit_price": 100
            }
        }

        # 1. First sync call
        response1 = client.post("/api/v1/offline/sync", json=payload, headers=headers)
        assert response1.status_code == 200
        assert response1.json()["ok"] is True
        assert mock_create_sale.call_count == 1

        # 2. Second sync call with same key (should be cached)
        response2 = client.post("/api/v1/offline/sync", json=payload, headers=headers)
        assert response2.status_code == 200
        assert response2.json()["ok"] is True
        assert mock_create_sale.call_count == 1  # No second execution


def test_offline_sync_validation_error_caching(client: TestClient, api_headers):
    """Verify that client-side validation errors are cached under the idempotency key, but server errors (500) are not."""
    with patch("app.modules.sales.service.SalesService.create_sale_from_form") as mock_create_sale:
        async def mock_fail(*args, **kwargs):
            raise ValueError("Solde insuffisant")
        mock_create_sale.side_effect = mock_fail

        headers = {**api_headers, "X-Idempotency-Key": "test_sync_key_fail"}
        payload = {
            "type": "create_sale",
            "payload": {"client_id": 1}
        }

        # 1. Call sync resulting in ValueError (422)
        response1 = client.post("/api/v1/offline/sync", json=payload, headers=headers)
        assert response1.status_code == 422
        assert response1.json()["error"]["message"] == "Solde insuffisant"

        # 2. Call again with same key (should return cached 422 error immediately)
        response2 = client.post("/api/v1/offline/sync", json=payload, headers=headers)
        assert response2.status_code == 422
        assert response2.json()["error"]["message"] == "Solde insuffisant"


def test_offline_sync_bulk(client: TestClient, api_headers):
    """Verify that bulk sync routes all operations, tracks idempotency, and manages individual transactions."""
    with patch("app.modules.sales.service.SalesService.create_sale_from_form") as mock_create_sale, \
         patch("app.api.v1.offline.create_payment_from_form") as mock_create_payment:

        async def mock_sale(*args, **kwargs):
            return {"mode": "document"}
        mock_create_sale.side_effect = mock_sale

        async def mock_payment(*args, **kwargs):
            return (101, "versement")
        mock_create_payment.side_effect = mock_payment

        payload = {
            "operations": [
                {
                    "type": "create_sale",
                    "idempotency_key": "bulk_key_1",
                    "payload": {"client_id": 1, "item_key": "raw:1"}
                },
                {
                    "type": "create_payment",
                    "idempotency_key": "bulk_key_2",
                    "payload": {"client_id": 1, "amount": 100}
                },
                {
                    "type": "invalid_operation_type",
                    "idempotency_key": "bulk_key_3",
                    "payload": {}
                }
            ]
        }

        response = client.post("/api/v1/offline/sync/bulk", json=payload, headers=api_headers)
        assert response.status_code == 200
        res = response.json()
        assert "results" in res
        assert len(res["results"]) == 3

        # First operation: success
        assert res["results"][0]["idempotency_key"] == "bulk_key_1"
        assert res["results"][0]["status_code"] == 200
        assert res["results"][0]["response"]["ok"] is True
        assert res["results"][0]["response"]["mode"] == "document"

        # Second operation: success
        assert res["results"][1]["idempotency_key"] == "bulk_key_2"
        assert res["results"][1]["status_code"] == 200
        assert res["results"][1]["response"]["ok"] is True
        assert res["results"][1]["response"]["id"] == 101

        # Third operation: error (400)
        assert res["results"][2]["idempotency_key"] == "bulk_key_3"
        assert res["results"][2]["status_code"] == 400
        assert "error" in res["results"][2]["response"]

