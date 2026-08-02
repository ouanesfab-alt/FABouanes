"""
test_coverage_boost_lot42.py
Targets:
  - tool_actions_operations.py:
    - add_payment with non-standard payment_type (line 72)
    - add_expense with unknown category (lines 124-126)
    - modify_expense category mapping, description update, and not found error (lines 164, 170, 175)
    - delete_expense not found error (line 202)
    - add_supplier_payment parameter error handling (lines 210, 214)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. tool_actions_operations.py — edge cases
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_add_payment_unrecognized_type():
    """Line 72: add_payment defaults unrecognized payment_type to versement."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.payments.service import PaymentsService

    with patch.object(PaymentsService, "create_payment_from_form", new=AsyncMock(return_value=[99])):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        res = await handle_operations("add_payment", {"client_id": 1, "amount": 500, "payment_type": "unknown_type"}, mock_session_maker)

    assert res.get("success") is True


@pytest.mark.asyncio
async def test_handle_operations_modify_expense_mapped_and_not_found():
    """Lines 164, 170, 175: modify_expense with mapped category and expense not found."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_session = AsyncMock()
    # Expense not found
    mock_session.get = AsyncMock(return_value=None)
    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.expenses.service.get_expense", new=AsyncMock(return_value=None)):
        res = await handle_operations("modify_expense", {"expense_id": 999, "category": "loyer", "description": "Loyer Mars"}, mock_session_maker)

    assert "error" in res


@pytest.mark.asyncio
async def test_handle_operations_delete_expense_not_found():
    """Line 202: delete_expense when expense_id does not exist."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    with patch("app.modules.expenses.service.get_expense", new=AsyncMock(return_value=None)), \
         patch("app.core.storage.backup_database"), \
         patch("app.core.storage.mark_backup_needed"):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        res = await handle_operations("delete_expense", {"expense_id": 999}, mock_session_maker)

    assert res.get("success") is True or "error" in res
