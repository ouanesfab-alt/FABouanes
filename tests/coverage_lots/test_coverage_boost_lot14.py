"""Tests de couverture ciblés — Lot 14.

Couvre: modules/sales/commands.py (create_sale_from_form document & line modes),
        assistant/tool_actions_operations.py (get_payment_status)
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema


# ── sales/commands.py (81% → target ~92%) ───────────────────────────


@pytest.mark.asyncio
async def test_create_sale_from_form_single_line():
    """create_sale_from_form with single line creates line-mode sale."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    with patch("app.modules.sales.validation.SalesValidator.validate_client", new_callable=AsyncMock), \
         patch("app.modules.sales.commands.SalesCommands.create_sale_record", new_callable=AsyncMock) as mock_record, \
         patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_detail, \
         patch("app.modules.sales.commands.invalidate_cache_domains"), \
         patch("app.modules.sales.commands.emit"):

        mock_record.return_value = ("finished", 42)
        mock_detail.return_value = {"id": 42, "total": 100.0}

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=None,
            notes="Vente directe",
            lines=[SaleLineSchema(item_key="finished:1", quantity=5.0, unit="kg", unit_price=20.0)]
        )

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "line"
        assert res["print_item_id"] == 42
        assert res["first_line_kind"] == "finished"


@pytest.mark.asyncio
async def test_create_sale_from_form_multi_line_document():
    """create_sale_from_form with multiple lines creates document-mode sale."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    doc_mock = MagicMock()
    doc_mock.model_dump.return_value = {"id": 100, "total": 200.0}

    with patch("app.modules.sales.validation.SalesValidator.validate_client", new_callable=AsyncMock), \
         patch("app.modules.sales.commands.SalesCommands._insert_sale_document", new_callable=AsyncMock) as mock_doc_id, \
         patch("app.modules.sales.commands.SalesCommands.create_sale_record", new_callable=AsyncMock) as mock_record, \
         patch("app.modules.sales.repository.SaleDocumentRepository.get_by_id", new_callable=AsyncMock) as mock_get_doc, \
         patch("app.modules.sales.commands.invalidate_cache_domains"), \
         patch("app.modules.sales.commands.emit"):

        mock_doc_id.return_value = 100
        mock_record.side_effect = [("finished", 1), ("raw", 2)]
        mock_get_doc.return_value = doc_mock

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=10,
            notes="Facture groupée",
            lines=[
                SaleLineSchema(item_key="finished:1", quantity=5.0, unit="kg", unit_price=20.0),
                SaleLineSchema(item_key="raw:2", quantity=2.0, unit="kg", unit_price=50.0),
            ]
        )

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "document"
        assert res["document_id"] == 100
        assert res["line_count"] == 2


# ── tool_actions_operations.py (85% → target ~95%) ─────────────────


@pytest.mark.asyncio
async def test_handle_operations_get_payment_status():
    """handle_operations get_payment_status fetches client and payment history."""
    from types import SimpleNamespace
    from app.modules.assistant.tool_actions_operations import handle_operations

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    client_obj = SimpleNamespace(id=5, name="Client Test", balance=2500.0)
    payment_obj = SimpleNamespace(id=1, client_id=5, amount=1000.0, payment_type="versement", payment_date=date.today(), notes="Règlement partiel")

    mock_session.get.return_value = client_obj

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [payment_obj]
    mock_session.execute.return_value = mock_res

    args = {"client_id": 5}
    res = await handle_operations("get_payment_status", args, session_maker)

    assert res.get("success") is True
    assert res.get("client", {}).get("name") == "Client Test"






