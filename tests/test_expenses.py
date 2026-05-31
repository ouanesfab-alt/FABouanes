"""
Tests unitaires et d'intégration pour le module Dépenses & Charges.
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from tests.test_services_coverage import client, MockAsyncSession
from app.core.models import Expense
from app.modules.expenses.repository import (
    get_all_expenses,
    get_expense_by_id,
    create_expense,
    update_expense,
    delete_expense,
    expenses_total,
    expenses_by_category,
    expenses_by_month,
)
from app.modules.expenses.service import (
    list_expenses,
    get_expense,
    add_expense,
    modify_expense,
    remove_expense,
    get_categories,
    get_payment_methods,
)


@pytest.mark.asyncio
async def test_expense_repository():
    db = MockAsyncSession()

    # Get all expenses
    results = await get_all_expenses(db, {"category": "transport", "date_from": "2026-01-01", "date_to": "2026-12-31", "q": "essence"})
    assert len(results) > 0
    assert isinstance(results[0], Expense)

    # Get by id
    res = await get_expense_by_id(db, 1)
    assert res is not None
    assert res.id == 1

    # Create expense
    new_id = await create_expense(db, date.today(), "transport", "Bus ticket", 2.5, "cash")
    assert new_id == 1

    # Create expense with string date
    new_id_str = await create_expense(db, "2026-05-31", "general", "Paper", 10.0, "cash")
    assert new_id_str == 1

    # Update expense
    await update_expense(db, 1, date.today(), "transport", "Taxi ride", 15.0, "virement")

    # Update expense with string date
    await update_expense(db, 1, "2026-05-31", "transport", "Taxi ride", 15.0, "virement")

    # Delete expense
    await delete_expense(db, 1)

    # Expenses aggregates
    total = await expenses_total(db, "2026-01-01", "2026-12-31")
    assert isinstance(total, float)

    by_cat = await expenses_by_category(db, "2026-01-01", "2026-12-31")
    assert isinstance(by_cat, list)

    by_month = await expenses_by_month(db)
    assert isinstance(by_month, list)


@pytest.mark.asyncio
async def test_expense_service():
    db = MockAsyncSession()

    # List
    lst = await list_expenses(db)
    assert len(lst) > 0

    # Get
    item = await get_expense(db, 1)
    assert item is not None

    # Add
    new_id = await add_expense(db, date.today(), "general", "Pens", 5.0, "cash")
    assert new_id == 1

    # Modify
    await modify_expense(db, 1, date.today(), "general", "Pens and notebooks", 12.0, "cash")

    # Remove
    success = await remove_expense(db, 1)
    assert success is True

    # Remove non-existent
    with patch("app.modules.expenses.service.get_expense_by_id", return_value=None):
        fail_success = await remove_expense(db, 999)
        assert fail_success is False

    # Helpers
    assert len(get_categories()) > 0
    assert len(get_payment_methods()) > 0


class TestExpenseWebRoutes:
    def test_expenses_page(self):
        response = client.get("/expenses")
        assert response.status_code == 200
        assert "Dépenses &amp; Charges" in response.text or "Dépenses" in response.text

    def test_new_expense_page(self):
        response = client.get("/expenses/new")
        assert response.status_code == 200
        assert "Nouvelle dépense" in response.text

    def test_new_expense_submit_success(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi standard",
            "amount": "15.50",
            "payment_method": "cash",
        }
        response = client.post("/expenses/new", data=payload, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/expenses"

    def test_new_expense_submit_validation_error(self):
        payload = {
            "date": "invalid-date",
            "category": "invalid-category",
            "description": "Taxi standard",
            "amount": "-5.00",
            "payment_method": "invalid-method",
        }
        response = client.post("/expenses/new", data=payload)
        assert response.status_code == 200
        assert "Erreur de validation" in response.text

    def test_new_expense_submit_friendly_error(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi",
            "amount": "15.50",
            "payment_method": "cash",
        }
        with patch("app.modules.expenses.web.add_expense", side_effect=ValueError("Duplicate entry")):
            response = client.post("/expenses/new", data=payload)
            assert response.status_code == 200
            assert "Duplicate entry" in response.text or "Erreur" in response.text

    def test_edit_expense_page(self):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 200
        assert "Modifier la dépense" in response.text

    def test_edit_expense_page_not_found(self):
        with patch("app.modules.expenses.web.get_expense", return_value=None):
            response = client.get("/expenses/999/edit", follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/expenses"

    def test_edit_expense_submit_success(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi updated",
            "amount": "17.50",
            "payment_method": "cash",
        }
        response = client.post("/expenses/{}/edit".format(1), data=payload, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/expenses"

    def test_edit_expense_submit_not_found(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi updated",
            "amount": "17.50",
            "payment_method": "cash",
        }
        with patch("app.modules.expenses.web.get_expense", return_value=None):
            response = client.post("/expenses/999/edit", data=payload, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/expenses"

    def test_edit_expense_submit_validation_error(self):
        payload = {
            "date": "invalid-date",
            "category": "invalid-category",
            "description": "Taxi standard",
            "amount": "-5.00",
            "payment_method": "invalid-method",
        }
        response = client.post("/expenses/1/edit", data=payload)
        assert response.status_code == 200
        assert "Erreur de validation" in response.text

    def test_edit_expense_submit_friendly_error(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi updated",
            "amount": "17.50",
            "payment_method": "cash",
        }
        with patch("app.modules.expenses.web.modify_expense", side_effect=ValueError("Update failed")):
            response = client.post("/expenses/1/edit", data=payload)
            assert response.status_code == 200
            assert "Update failed" in response.text or "Erreur" in response.text

    def test_delete_expense_success(self):
        response = client.post("/expenses/1/delete", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/expenses"

    def test_delete_expense_not_found(self):
        with patch("app.modules.expenses.web.remove_expense", return_value=False):
            response = client.post("/expenses/999/delete", follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/expenses"


class TestExpenseApiEndpoints:
    def test_api_list_expenses(self):
        response = client.get("/api/v1/expenses")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_api_get_expense_detail(self):
        response = client.get("/api/v1/expenses/1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == 1

    def test_api_get_expense_detail_not_found(self):
        with patch("app.api.v1.expenses.get_expense", return_value=None):
            response = client.get("/api/v1/expenses/999")
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert "introuvable" in data["error"]["message"]

    def test_api_create_expense_success(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi API",
            "amount": 25.0,
            "payment_method": "cash",
        }
        response = client.post("/api/v1/expenses", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["amount"] == 100.0  # mocked return from mock_sqlmodel_instance

    def test_api_create_expense_internal_error(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi API",
            "amount": 25.0,
            "payment_method": "cash",
        }
        with patch("app.api.v1.expenses.get_expense", return_value=None):
            response = client.post("/api/v1/expenses", json=payload)
            assert response.status_code == 500

    def test_api_update_expense_success(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi API updated",
            "amount": 30.0,
            "payment_method": "virement",
        }
        response = client.put("/api/v1/expenses/1", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_api_update_expense_not_found(self):
        payload = {
            "date": "2026-05-31",
            "category": "transport",
            "description": "Taxi API updated",
            "amount": 30.0,
            "payment_method": "virement",
        }
        with patch("app.api.v1.expenses.get_expense", return_value=None):
            response = client.put("/api/v1/expenses/999", json=payload)
            assert response.status_code == 404

    def test_api_delete_expense_success(self):
        response = client.delete("/api/v1/expenses/1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True

    def test_api_delete_expense_not_found(self):
        with patch("app.api.v1.expenses.remove_expense", return_value=False):
            response = client.delete("/api/v1/expenses/999")
            assert response.status_code == 404
