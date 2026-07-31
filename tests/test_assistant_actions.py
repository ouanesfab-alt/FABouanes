"""Suite complète et consolidée de tests unitaires pour les modules Assistant FABOuanes (Sabrina)."""
from __future__ import annotations

import pytest
from unittest import mock

from app.modules.assistant.tool_actions_operations import handle_operations
from app.modules.assistant.tool_actions_contacts import handle_contacts
from app.modules.assistant.rag import search_manual, update_pdf_index, search_user_documents


@pytest.mark.asyncio
async def test_assistant_contacts_all_actions():
    mock_session = mock.AsyncMock()
    mock_session.execute.return_value.scalar = mock.MagicMock(return_value=0)
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    # 1. add_client
    mock_client = mock.MagicMock()
    mock_client.id = 42
    with mock.patch("app.modules.clients.service.ClientService.create_client", mock.AsyncMock(return_value=mock_client)):
        res = await handle_contacts("add_client", {"name": "Client Test 42", "phone": "0550123456"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 2. modify_client
    mock_client_existing = mock.MagicMock()
    mock_client_existing.name = "Client Existant"
    with mock.patch("app.modules.clients.service.ClientService.get_client", mock.AsyncMock(return_value=mock_client_existing)), \
         mock.patch("app.modules.clients.service.ClientService.update_client", mock.AsyncMock(return_value=mock_client_existing)):
        res = await handle_contacts("modify_client", {"client_id": 42, "name": "Nouveau Nom"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 3. delete_client
    with mock.patch("app.modules.clients.service.ClientService.delete_client", mock.AsyncMock(return_value=True)):
        res = await handle_contacts("delete_client", {"client_id": 42}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 4. add_supplier
    with mock.patch("app.services.contact_directory_service.create_supplier_from_form", mock.AsyncMock(return_value=10)):
        res = await handle_contacts("add_supplier", {"name": "Fournisseur Alpha", "phone": "021000000"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 5. modify_supplier
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value={"name": "Alpha"})), \
         mock.patch("app.services.contact_directory_service.update_supplier_from_form", mock.AsyncMock(return_value=None)):
        res = await handle_contacts("modify_supplier", {"supplier_id": 10, "name": "Fournisseur Beta"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 6. delete_supplier
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value={"name": "Beta"})), \
         mock.patch("app.services.contact_directory_service.delete_supplier_by_id", mock.AsyncMock(return_value=None)):
        res = await handle_contacts("delete_supplier", {"supplier_id": 10}, mock_session_maker)
        assert res is not None and res.get("success") is True


@pytest.mark.asyncio
async def test_handle_contacts_modify_delete_not_found():
    mock_session = mock.AsyncMock()
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    with mock.patch("app.modules.clients.service.ClientService.update_client", mock.AsyncMock(return_value=None)):
        res_mod = await handle_contacts("modify_client", {"client_id": 999999, "name": "Nouveau Nom"}, mock_session_maker)
        assert res_mod is not None and "error" in res_mod

    with mock.patch("app.modules.clients.service.ClientService.delete_client", mock.AsyncMock(return_value=False)):
        res_del = await handle_contacts("delete_client", {"client_id": 999999}, mock_session_maker)
        assert res_del is not None and "error" in res_del

    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value=None)):
        res_supp = await handle_contacts("modify_supplier", {"supplier_id": 999999, "name": "Fournisseur Test"}, mock_session_maker)
        assert res_supp is not None and "error" in res_supp

    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value=None)):
        res_del_supp = await handle_contacts("delete_supplier", {"supplier_id": 999999}, mock_session_maker)
        assert res_del_supp is not None and "error" in res_del_supp


@pytest.mark.asyncio
async def test_assistant_operations_all_actions():
    mock_session = mock.AsyncMock()
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    # 1. add_sale
    with mock.patch("app.modules.sales.service.SalesService.create_sale_from_form", mock.AsyncMock(return_value={"sale_id": 100})):
        res = await handle_operations(
            "add_sale",
            {"item_kind": "finished", "finished_product_id": 1, "quantity": 10, "unit_price": 50, "amount_paid": 500},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True

    # 2. add_purchase
    with mock.patch("app.modules.purchases.service.PurchaseService.create_purchase_from_form", mock.AsyncMock(return_value={"purchase_id": 200})):
        res = await handle_operations(
            "add_purchase",
            {"item_kind": "raw", "raw_material_id": 2, "quantity": 50, "unit_price": 20},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True

    # 3. add_payment
    with mock.patch("app.modules.payments.service.PaymentsService.create_payment_from_form", mock.AsyncMock(return_value=(300,))):
        res = await handle_operations(
            "add_payment",
            {"client_id": 1, "amount": 250, "payment_type": "versement"},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True

    # 4. add_expense
    with mock.patch("app.modules.expenses.service.add_expense", mock.AsyncMock(return_value=400)):
        res = await handle_operations(
            "add_expense",
            {"category": "transport", "amount": 120, "description": "Frais livraison"},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True

    # 5. modify_expense
    mock_exp = mock.MagicMock()
    mock_exp.date = "2026-01-01"
    mock_exp.category = "transport"
    mock_exp.amount = 120.0
    mock_exp.description = "Test"
    mock_exp.payment_method = "cash"
    with mock.patch("app.modules.expenses.service.get_expense", mock.AsyncMock(return_value=mock_exp)), \
         mock.patch("app.modules.expenses.service.modify_expense", mock.AsyncMock(return_value=True)):
        res = await handle_operations(
            "modify_expense",
            {"expense_id": 400, "amount": 150},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True

    # 6. delete_expense
    with mock.patch("app.modules.expenses.service.remove_expense", mock.AsyncMock(return_value=True)):
        res = await handle_operations(
            "delete_expense",
            {"expense_id": 400},
            mock_session_maker
        )
        assert res is not None and res.get("success") is True


@pytest.mark.asyncio
async def test_get_export_link_and_invoices():
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

    # create_invoice_document missing lines
    res_err = await handle_operations("create_invoice_document", {"client_id": 1}, session_maker)
    assert res_err is not None and "error" in res_err

    # create_invoice_document invalid date error
    res_date_err = await handle_operations("create_invoice_document", {"sale_date": "invalid-date", "lines": [{"item_key": "finished:1"}]}, session_maker)
    assert res_date_err is not None and "error" in res_date_err

    # create_invoice_document success
    mock_session = mock.AsyncMock()
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)
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


def test_rag_helpers():
    manual_results = search_manual("facture vente", limit=5)
    assert isinstance(manual_results, list)

    pdf_index = update_pdf_index()
    assert isinstance(pdf_index, dict)

    pdf_results = search_user_documents("stock produit", limit=3)
    assert isinstance(pdf_results, list)
