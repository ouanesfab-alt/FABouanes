from __future__ import annotations

import pytest
from app.modules.expenses.service import add_expense, get_expense, modify_expense, list_expenses, remove_expense


def test_create_and_delete_expense():
    # 1. Test insertion
    expense_id = add_expense(
        date="2026-05-18",
        category="transport",
        description="Essence camion de livraison",
        amount=65.50,
        method="cash"
    )
    assert expense_id > 0

    # 2. Get and verify
    expense = get_expense(expense_id)
    assert expense is not None
    assert expense["category"] == "transport"
    assert expense["description"] == "Essence camion de livraison"
    assert float(expense["amount"]) == 65.50
    assert expense["payment_method"] == "cash"

    # 3. Test update
    modify_expense(
        expense_id=expense_id,
        date="2026-05-19",
        category="fournitures",
        description="Essence camion de livraison - MAJ",
        amount=70.00,
        method="virement"
    )
    
    updated = get_expense(expense_id)
    assert updated is not None
    assert updated["category"] == "fournitures"
    assert updated["description"] == "Essence camion de livraison - MAJ"
    assert float(updated["amount"]) == 70.00
    assert updated["payment_method"] == "virement"

    # 4. Test listing and filters
    # Filter by category
    transport_list = list_expenses({"category": "transport"})
    assert not any(e["id"] == expense_id for e in transport_list)

    fournitures_list = list_expenses({"category": "fournitures"})
    assert any(e["id"] == expense_id for e in fournitures_list)

    # Filter by search text
    search_list = list_expenses({"q": "livraison"})
    assert any(e["id"] == expense_id for e in search_list)

    # Filter by date ranges
    in_range = list_expenses({"date_from": "2026-05-18", "date_to": "2026-05-20"})
    assert any(e["id"] == expense_id for e in in_range)

    out_of_range = list_expenses({"date_from": "2026-05-21"})
    assert not any(e["id"] == expense_id for e in out_of_range)

    # 5. Clean up / deletion
    assert remove_expense(expense_id) is True
    assert get_expense(expense_id) is None
    assert remove_expense(expense_id) is False
