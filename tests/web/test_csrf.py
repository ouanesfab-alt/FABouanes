from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.conftest import extract_csrf
from app.core.db_access import execute_db


def test_csrf_scenarios(logged_client):
    # 1. Open the new client page to load session/CSRF
    page = logged_client.get("/contacts/clients/new")
    assert page.status_code == 200
    correct_csrf = extract_csrf(page.text)
    
    # 2. POST without CSRF token -> should return 403
    response_no_csrf = logged_client.post(
        "/contacts/clients/new",
        data={
            "name": "No CSRF Client",
            "phone": "0555000000",
            "address": "No CSRF Rd",
            "opening_credit": "0.00",
            "notes": "No CSRF"
        },
        follow_redirects=False
    )
    assert response_no_csrf.status_code == 403
    assert "CSRF token invalid" in response_no_csrf.text
    
    # 3. POST with wrong CSRF token -> should return 403
    response_wrong_csrf = logged_client.post(
        "/contacts/clients/new",
        data={
            "csrf_token": "wrong_token_here",
            "name": "Wrong CSRF Client",
            "phone": "0555000000",
            "address": "Wrong CSRF Rd",
            "opening_credit": "0.00",
            "notes": "Wrong CSRF"
        },
        follow_redirects=False
    )
    assert response_wrong_csrf.status_code == 403
    assert "CSRF token invalid" in response_wrong_csrf.text
    
    # 4. POST with correct CSRF token -> should succeed (303 redirect)
    response_correct = logged_client.post(
        "/contacts/clients/new",
        data={
            "csrf_token": correct_csrf,
            "name": "Correct CSRF Client",
            "phone": "0555000000",
            "address": "Correct CSRF Rd",
            "opening_credit": "0.00",
            "notes": "Correct CSRF"
        },
        follow_redirects=False
    )
    assert response_correct.status_code == 303
    
    # Clean up
    execute_db("DELETE FROM clients WHERE name = %s", ("Correct CSRF Client",))
