"""Tests de couverture ciblés — Lot 13.

Couvre: assistant/tool_actions_contacts.py (import_client_excel, import_client_history_excel, import_bulk_clients_excel),
        modules/sales/commands.py (create_sale_record)
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.assistant.tool_actions_contacts import handle_contacts


# ── tool_actions_contacts.py Excel Imports (77% → target ~95%) ───────


@pytest.mark.asyncio
async def test_handle_contacts_import_client_excel_outside_workspace():
    """import_client_excel rejects files outside workspace directory."""
    session_maker = MagicMock()
    res = await handle_contacts("import_client_excel", {"filepath": "../../outside.xlsx"}, session_maker)
    assert "error" in res
    assert "Accès interdit" in res["error"] or "Sécurité" in res["error"]



@pytest.mark.asyncio
async def test_handle_contacts_import_client_excel_parse_error():
    """import_client_excel returns error message if Excel parsing fails."""
    session_maker = MagicMock()

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_client_file", side_effect=ValueError("Fichier corrompu")):

        res = await handle_contacts("import_client_excel", {"filepath": "test.xlsx"}, session_maker)
        assert "error" in res
        assert "corrompu" in res["error"] or "Excel" in res["error"]


@pytest.mark.asyncio
async def test_handle_contacts_import_client_history_excel_outside_workspace():
    """import_client_history_excel rejects files outside workspace."""
    session_maker = MagicMock()
    res = await handle_contacts("import_client_history_excel", {"filepath": "../../outside.xlsx"}, session_maker)
    assert "error" in res


@pytest.mark.asyncio
async def test_handle_contacts_import_client_history_excel_success():
    """import_client_history_excel imports history and returns success dict."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    import_res = {"client_name": "Client Importé", "nb_lignes": 15, "solde_final": 5000.0}

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.modules.clients.service.ClientService") as mock_srv_cls:

        mock_srv = AsyncMock()
        mock_srv.import_client_history_from_excel.return_value = import_res
        mock_srv_cls.return_value = mock_srv

        args = {"filepath": "client_hist.xlsx", "client_id": 1}
        res = await handle_contacts("import_client_history_excel", args, session_maker)

        assert res.get("success") is True
        assert "Client Importé" in res.get("message", "")


@pytest.mark.asyncio
async def test_handle_contacts_import_bulk_clients_excel_success():
    """import_bulk_clients_excel imports multiple clients from Excel file."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    parsed_clients = [
        {"name": "Client A", "phone": "0550111111", "address": "", "notes": "", "opening_credit": 0.0},
        {"name": "Client B", "phone": "0550222222", "address": "", "notes": "", "opening_credit": 100.0},
    ]

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_clients", return_value=parsed_clients), \
         patch("app.modules.clients.service.ClientService") as mock_srv_cls:

        mock_srv = AsyncMock()
        mock_srv_cls.return_value = mock_srv

        args = {"filepath": "bulk_clients.xlsx"}
        res = await handle_contacts("import_bulk_clients_excel", args, session_maker)

        assert res.get("success") is True
        assert "2/2" in res.get("message", "")


# ── sales/commands.py (81% → target ~90%) ───────────────────────────


@pytest.mark.asyncio
async def test_create_sale_record_cash_finished():
    """create_sale_record creates sale record for cash sale with finished product."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    item_mock = MagicMock()
    item_mock.stock_qty = 50.0
    item_mock.avg_cost = 10.0

    with patch("app.modules.sales.validation.SalesValidator.validate_stock_availability", new_callable=AsyncMock) as mock_avail, \
         patch("app.modules.sales.commands.SalesCommands.record_stock_movement", new_callable=AsyncMock), \
         patch("app.modules.sales.commands.invalidate_cache_domains"), \
         patch("app.modules.sales.commands.emit"):

        mock_avail.return_value = (item_mock, 10.0)

        cmd = SalesCommands(session)
        kind, sale_id = await cmd.create_sale_record(
            client_id=None,
            item_kind="finished",
            item_id=1,
            qty=10.0,
            unit="kg",
            unit_price=20.0,
            sale_type="cash",
            sale_date=date.today(),
            notes="Vente test"
        )

        assert kind == "finished"
        assert session.add.called
