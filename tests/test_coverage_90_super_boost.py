"""Tests d'intégration et unitaires massifs pour garantir la couverture Python Core > 90%."""
from __future__ import annotations

import os
import pytest
from unittest import mock

from app.core.db_helpers.manager import DatabaseManager
from app.modules.assistant.rag import search_manual, update_pdf_index, search_user_documents
from app.modules.assistant.sql_tools import dry_run_sql, serialize_for_json
from app.modules.assistant.tool_actions_contacts import handle_contacts
from app.modules.assistant.tool_actions_operations import handle_operations


@pytest.mark.asyncio
async def test_assistant_contacts_all_actions():
    mock_session = mock.AsyncMock()
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    # 1. add_client with mock client creation
    mock_client = mock.MagicMock()
    mock_client.id = 42
    with mock.patch("app.modules.clients.service.ClientService.create_client", mock.AsyncMock(return_value=mock_client)):
        res = await handle_contacts("add_client", {"name": "Client Test 42", "phone": "0550123456"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 2. modify_client with mock update
    mock_client_existing = mock.MagicMock()
    mock_client_existing.name = "Client Existant"
    with mock.patch("app.modules.clients.service.ClientService.get_client", mock.AsyncMock(return_value=mock_client_existing)), \
         mock.patch("app.modules.clients.service.ClientService.update_client", mock.AsyncMock(return_value=mock_client_existing)):
        res = await handle_contacts("modify_client", {"client_id": 42, "name": "Nouveau Nom"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 3. delete_client with mock delete
    with mock.patch("app.modules.clients.service.ClientService.delete_client", mock.AsyncMock(return_value=True)):
        res = await handle_contacts("delete_client", {"client_id": 42}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 4. add_supplier with mock create
    with mock.patch("app.services.contact_directory_service.create_supplier_from_form", mock.AsyncMock(return_value=10)):
        res = await handle_contacts("add_supplier", {"name": "Fournisseur Alpha", "phone": "021000000"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 5. modify_supplier with mock update
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value={"name": "Alpha"})), \
         mock.patch("app.services.contact_directory_service.update_supplier_from_form", mock.AsyncMock(return_value=None)):
        res = await handle_contacts("modify_supplier", {"supplier_id": 10, "name": "Fournisseur Beta"}, mock_session_maker)
        assert res is not None and res.get("success") is True

    # 6. delete_supplier with no associated purchases
    mock_session.execute.return_value.scalar = mock.MagicMock(return_value=0)
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value={"name": "Beta"})), \
         mock.patch("app.services.contact_directory_service.delete_supplier_by_id", mock.AsyncMock(return_value=None)):
        res = await handle_contacts("delete_supplier", {"supplier_id": 10}, mock_session_maker)
        assert res is not None and res.get("success") is True


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


def test_rag_and_db_manager_helpers():
    manual_results = search_manual("facture vente", limit=5)
    assert isinstance(manual_results, list)

    pdf_index = update_pdf_index()
    assert isinstance(pdf_index, dict)

    pdf_results = search_user_documents("stock produit", limit=3)
    assert isinstance(pdf_results, list)

    mgr = DatabaseManager()
    assert mgr.sqlalchemy_database_url("postgres://user:pass@host/db") == "postgresql+pg8000://user:pass@host/db"
    assert mgr._postgres_last_insert_id(mock.MagicMock(), "SELECT 1") == 0
