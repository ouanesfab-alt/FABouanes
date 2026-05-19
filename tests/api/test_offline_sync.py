from __future__ import annotations

import re

from app.core.db_access import query_db


def _extract_meta_csrf(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert match, "csrf meta token not found"
    return match.group(1)


def test_offline_reference_data_uses_web_session(logged_client):
    response = logged_client.get("/api/v1/offline/reference-data")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["clients"]
    assert payload["catalog"]


def test_offline_sync_is_idempotent_for_web_session(logged_client, first_client_id):
    page = logged_client.get("/operations/new?mode=versement")
    csrf_token = _extract_meta_csrf(page.text)
    operation_id = "offline-test-payment-001"
    payload = {
        "client_operation_id": operation_id,
        "type": "create_payment",
        "payload": {
            "client_id": str(first_client_id),
            "amount": "10",
            "payment_date": "2026-05-19",
            "payment_type": "avance",
            "notes": "offline idempotency test",
        },
    }

    first = logged_client.post("/api/v1/offline/sync", json=payload, headers={"X-CSRF-Token": csrf_token})
    second = logged_client.post("/api/v1/offline/sync", json=payload, headers={"X-CSRF-Token": csrf_token})

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["duplicate"] is True

    row = query_db(
        "SELECT COUNT(*) AS count FROM payments WHERE notes = %s",
        ("offline idempotency test",),
        one=True,
    )
    assert int(row["count"]) == 1

    receipt = query_db(
        """
        SELECT status
        FROM offline_operation_receipts
        WHERE client_operation_id = %s
        """,
        (operation_id,),
        one=True,
    )
    assert receipt["status"] == "success"
