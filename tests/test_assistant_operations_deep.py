"""Tests unitaires ciblés pour app/modules/assistant/tool_actions_operations.py et tool_actions_contacts.py."""
from __future__ import annotations

import pytest
from unittest import mock
from pydantic import ValidationError

from app.modules.assistant.tool_actions_operations import handle_operations
from app.modules.assistant.tool_actions_contacts import handle_contacts


@pytest.mark.asyncio
async def test_handle_operations_validation_errors_and_queries():
    session_maker = mock.MagicMock()

    # add_sale without item_id
    res_sale = await handle_operations("add_sale", {}, session_maker)
    assert res_sale is not None
    assert "error" in res_sale

    # add_purchase without item_id
    res_pur = await handle_operations("add_purchase", {}, session_maker)
    assert res_pur is not None
    assert "error" in res_pur

    # delete_operation with mocked service failure
    with mock.patch("app.modules.payments.service.PaymentsService.delete_payment_by_id", mock.AsyncMock(return_value=False)):
        mock_session = mock.AsyncMock()
        mock_cm = mock.MagicMock()
        mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
        mock_session_maker = mock.MagicMock(return_value=mock_cm)

        res_del = await handle_operations("delete_operation", {"tx_kind": "payment", "tx_id": 999999}, mock_session_maker)
        assert res_del is not None
        assert "error" in res_del

    # generate_quote
    res_quote = await handle_operations("generate_quote", {"client_name": "Client Proforma", "lines": [{"item_name": "Ciment", "quantity": 10, "unit_price": 500}]}, session_maker)
    assert res_quote is not None and res_quote.get("success") is True

    # get_stock_status
    exec_res = mock.MagicMock()
    exec_res.scalars.return_value.all.return_value = []
    mock_session = mock.AsyncMock()
    mock_session.execute = mock.AsyncMock(return_value=exec_res)
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    res_stock = await handle_operations("get_stock_status", {"product_type": "all"}, mock_session_maker)
    assert res_stock is not None and res_stock.get("success") is True

    # get_payment_status
    mock_session.get = mock.AsyncMock(return_value=None)
    res_pay_status = await handle_operations("get_payment_status", {"client_id": 1}, mock_session_maker)
    assert res_pay_status is not None and res_pay_status.get("success") is True

    # unknown func_name returns None
    res_unknown = await handle_operations("unknown_action", {}, session_maker)
    assert res_unknown is None


@pytest.mark.asyncio
async def test_handle_contacts_actions():
    session_maker = mock.MagicMock()

    with pytest.raises(ValidationError):
        await handle_contacts("add_client", {}, session_maker)

    with pytest.raises(ValidationError):
        await handle_contacts("add_supplier", {}, session_maker)

    res_unknown = await handle_contacts("unknown_action", {}, session_maker)
    assert res_unknown is None
