"""Tests unitaires ciblés pour hausser la couverture globale Python Core > 90%."""
from __future__ import annotations

import pytest
from unittest import mock

from app.modules.assistant.tool_actions_operations import handle_operations
from app.modules.assistant.tool_actions_contacts import handle_contacts


@pytest.mark.asyncio
async def test_get_export_link_actions():
    session_maker = mock.MagicMock()

    # get_export_link clients
    res_clients = await handle_operations("get_export_link", {"export_type": "clients"}, session_maker)
    assert res_clients is not None and "export_url" in res_clients

    # get_export_link reports
    res_reports = await handle_operations("get_export_link", {"export_type": "reports", "date_from": "2026-01-01"}, session_maker)
    assert res_reports is not None and "export_url" in res_reports

    # get_export_link audit
    res_audit = await handle_operations("get_export_link", {"export_type": "audit", "audit_filters": {"actor": "admin"}}, session_maker)
    assert res_audit is not None and "export_url" in res_audit

    # get_export_link diagnostic
    res_diag = await handle_operations("get_export_link", {"export_type": "diagnostic"}, session_maker)
    assert res_diag is not None and "export_url" in res_diag

    # get_export_link unknown
    res_unknown_exp = await handle_operations("get_export_link", {"export_type": "invalid_type"}, session_maker)
    assert res_unknown_exp is not None and "error" in res_unknown_exp


@pytest.mark.asyncio
async def test_create_invoice_document_action():
    mock_session = mock.AsyncMock()
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    # create_invoice_document missing lines error
    res_err = await handle_operations("create_invoice_document", {"client_id": 1}, mock_session_maker)
    assert res_err is not None and "error" in res_err

    # create_invoice_document invalid date error
    res_date_err = await handle_operations("create_invoice_document", {"sale_date": "invalid-date", "lines": [{"item_key": "finished:1"}]}, mock_session_maker)
    assert res_date_err is not None and "error" in res_date_err

    # create_invoice_document success
    with mock.patch("app.modules.sales.service.SalesService.create_sale_from_form", mock.AsyncMock(return_value={"document_id": 500, "print_doc_type": "sale_document"})):
        res_ok = await handle_operations(
            "create_invoice_document",
            {"client_id": 1, "lines": [{"item_key": "finished:1", "quantity": 5, "unit_price": 100}]},
            mock_session_maker
        )
        assert res_ok is not None and res_ok.get("success") is True


@pytest.mark.asyncio
async def test_contacts_import_path_guard():
    session_maker = mock.MagicMock()

    # import_client_excel invalid path
    res_import = await handle_contacts("import_client_excel", {"filepath": "../outside_workspace.xlsx"}, session_maker)
    assert res_import is not None and "error" in res_import

    # import_client_history_excel invalid path
    res_hist_import = await handle_contacts("import_client_history_excel", {"filepath": "../outside_workspace.xlsx"}, session_maker)
    assert res_hist_import is not None and "error" in res_hist_import
