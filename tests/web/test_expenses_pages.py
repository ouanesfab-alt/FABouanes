from __future__ import annotations

from app.modules.expenses.service import add_expense, get_expense, list_expenses, remove_expense
from tests.conftest import extract_csrf


def test_expenses_page_renders(logged_client):
    response = logged_client.get("/expenses")
    assert response.status_code == 200
    assert "Dépenses" in response.text or "Charges" in response.text


def test_new_expense_form_renders(logged_client):
    response = logged_client.get("/expenses/new")
    assert response.status_code == 200
    assert "Nouvelle dépense" in response.text


def test_create_expense_via_form_with_validation(logged_client):
    # 1. Fetch form to extract CSRF token
    page = logged_client.get("/expenses/new")
    csrf_token = extract_csrf(page.text)

    # 2. Post a valid expense form
    response = logged_client.post(
        "/expenses/new",
        data={
            "csrf_token": csrf_token,
            "date": "2026-05-18",
            "category": "transport",
            "description": "Form integration test",
            "amount": "1 250,80",  # Test European comma format parsing
            "payment_method": "cash"
        },
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/expenses"

    # 3. Verify it was correctly inserted with correct float amount
    all_expenses = list_expenses({"q": "Form integration test"})
    assert len(all_expenses) > 0
    expense = all_expenses[0]
    assert expense["category"] == "transport"
    assert float(expense["amount"]) == 1250.80

    # Cleanup
    remove_expense(expense["id"])


def test_create_expense_validation_error(logged_client):
    page = logged_client.get("/expenses/new")
    csrf_token = extract_csrf(page.text)

    # Submit an invalid amount
    response = logged_client.post(
        "/expenses/new",
        data={
            "csrf_token": csrf_token,
            "date": "2026-05-18",
            "category": "transport",
            "description": "Invalid amount test",
            "amount": "-50",  # Invalid negative amount
            "payment_method": "cash"
        },
        follow_redirects=False
    )
    assert response.status_code == 200  # Stays on page with template response
    assert "Erreur de validation" in response.text


def test_edit_expense_renders_and_submits(logged_client):
    # 1. Create a dummy expense
    expense_id = add_expense(
        date="2026-05-18",
        category="general",
        description="Dummy to edit",
        amount=100.00,
        method="cash"
    )

    # 2. Get edit page
    page = logged_client.get(f"/expenses/{expense_id}/edit")
    assert page.status_code == 200
    assert "Modifier" in page.text
    csrf_token = extract_csrf(page.text)

    # 3. Submit updated values
    response = logged_client.post(
        f"/expenses/{expense_id}/edit",
        data={
            "csrf_token": csrf_token,
            "date": "2026-05-19",
            "category": "loyer",
            "description": "Dummy to edit - Edited",
            "amount": "250.00",
            "payment_method": "virement"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    # 4. Verify updates
    updated = get_expense(expense_id)
    assert updated is not None
    assert updated["category"] == "loyer"
    assert float(updated["amount"]) == 250.00
    assert updated["payment_method"] == "virement"

    # Cleanup
    remove_expense(expense_id)


def test_delete_expense_route(logged_client):
    expense_id = add_expense(
        date="2026-05-18",
        category="general",
        description="Dummy to delete",
        amount=100.00,
        method="cash"
    )

    # Get page to extract CSRF
    page = logged_client.get("/expenses")
    csrf_token = extract_csrf(page.text)

    # Post delete
    response = logged_client.post(
        f"/expenses/{expense_id}/delete",
        data={"csrf_token": csrf_token},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert get_expense(expense_id) is None
