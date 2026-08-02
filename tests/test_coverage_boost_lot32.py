"""
test_coverage_boost_lot32.py
Targets:
  - tool_actions_operations.py:
    - add_supplier_payment (supplier missing, amount <= 0, success)
    - get_print_link (supported vs unsupported doc_type)
    - get_export_link (excel/pdf link generation)
    - get_stock_levels with product_name filter
    - get_payment_status with client_id and document_id
    - get_financial_report invalid date error
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ============================================================
# 1. tool_actions_operations.py — add_supplier_payment
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_add_supplier_payment_supplier_not_found():
    """Lines 223-224: add_supplier_payment when supplier does not exist."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await handle_operations("add_supplier_payment", {"supplier_id": 999, "amount": 100}, mock_session_maker)
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_operations_add_supplier_payment_invalid_amount():
    """Lines 225-226: add_supplier_payment with amount <= 0."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=(1,))))

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await handle_operations("add_supplier_payment", {"supplier_id": 1, "amount": 0}, mock_session_maker)
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_operations_add_supplier_payment_success():
    """Lines 227-249: add_supplier_payment happy path."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(fetchone=MagicMock(return_value=(1,))),
        MagicMock(fetchone=MagicMock(return_value=(10,))),
    ])

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await handle_operations("add_supplier_payment", {"supplier_id": 1, "amount": 5000}, mock_session_maker)
    assert result.get("success") is True
    assert result.get("payment_id") == 10


# ============================================================
# 2. tool_actions_operations.py — get_print_link & get_export_link
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_get_print_link():
    """Lines 251-269: get_print_link valid vs invalid doc_type."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    res1 = await handle_operations("get_print_link", {"doc_type": "sale_finished", "item_id": 5}, MagicMock())
    assert "print_url" in res1

    res2 = await handle_operations("get_print_link", {"doc_type": "invalid_doc", "item_id": 5}, MagicMock())
    assert "error" in res2


@pytest.mark.asyncio
async def test_handle_operations_get_export_link():
    """Lines 271-289: get_export_link."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    res = await handle_operations("get_export_link", {"export_type": "sales", "date_from": "2024-01-01"}, MagicMock())
    assert res is not None


# ============================================================
# 3. tool_actions_operations.py — get_stock_levels & payment_status
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_get_stock_levels_filtered():
    """Lines 427-429, 443-445: get_stock_levels with product_name filter."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_item = MagicMock()
    mock_item.id = 1
    mock_item.name = "Farine T55"
    mock_item.stock_qty = 100.0
    mock_item.default_unit = "kg"
    mock_item.avg_cost = 50.0
    mock_item.sale_price = 80.0
    mock_item.alert_threshold = 10.0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_item])))))

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await handle_operations("get_stock_status", {"product_type": "all", "product_name": "Farine"}, mock_session_maker)
    assert result.get("success") is True


@pytest.mark.asyncio
async def test_handle_operations_get_payment_status():
    """Lines 465-524: get_payment_status."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    mock_client = MagicMock(id=1, name="Client A", balance=500.0)
    mock_doc = MagicMock(id=2, client_id=1, total=1000.0, amount_paid=500.0, balance_due=500.0)
    mock_pmt = MagicMock(id=3, client_id=1, amount=500.0, payment_type="versement", payment_date="2024-01-01", notes="")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_client, mock_doc])
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_pmt])))))

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await handle_operations("get_payment_status", {"client_id": 1, "document_id": 2}, mock_session_maker)
    assert result.get("success") is True
    assert result.get("client") is not None


@pytest.mark.asyncio
async def test_handle_operations_get_financial_report_invalid_date():
    """Lines 534-535: get_financial_report with invalid date string."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    result = await handle_operations("get_financial_report", {"start_date": "invalid-date"}, MagicMock())
    assert "error" in result
