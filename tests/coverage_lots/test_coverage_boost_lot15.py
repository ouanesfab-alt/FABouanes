"""Tests de couverture ciblés — Lot 15.

Couvre: modules/sales/commands.py (edit_single_sale_from_form document conversion),
        modules/sales/queries.py (get_sale_document_context)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema


# ── sales/commands.py (81% → target ~92%) ───────────────────────────


@pytest.mark.asyncio
async def test_edit_single_sale_from_form_convert_to_document():
    """edit_single_sale_from_form converts single line sale to multi-line document sale."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    before_detail = {
        "id": 10,
        "client_id": 5,
        "quantity": 2.0,
        "unit_price": 50.0,
        "document_id": None,
    }

    doc_mock = MagicMock()
    doc_mock.model_dump.return_value = {"id": 200, "total": 300.0}

    with patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_before, \
         patch("app.modules.sales.validation.SalesValidator.validate_client", new_callable=AsyncMock), \
         patch("app.modules.sales.commands.SalesCommands._insert_sale_document", new_callable=AsyncMock) as mock_ins_doc, \
         patch("app.modules.sales.commands.SalesCommands.reverse_sale", new_callable=AsyncMock) as mock_rev, \
         patch("app.modules.sales.commands.SalesCommands.create_sale_record", new_callable=AsyncMock) as mock_rec, \
         patch("app.modules.sales.repository.SaleDocumentRepository.get_by_id", new_callable=AsyncMock) as mock_get_doc, \
         patch("app.modules.sales.commands.invalidate_cache_domains"), \
         patch("app.modules.sales.commands.emit"):

        mock_before.return_value = before_detail
        mock_ins_doc.return_value = 200
        mock_rev.return_value = True
        mock_rec.side_effect = [("finished", 1), ("raw", 2)]
        mock_get_doc.return_value = doc_mock

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=5,
            notes="Correction vente",
            lines=[
                SaleLineSchema(item_key="finished:1", quantity=3.0, unit="kg", unit_price=50.0),
                SaleLineSchema(item_key="raw:2", quantity=1.0, unit="kg", unit_price=150.0),
            ]
        )

        res = await cmd.edit_single_sale_from_form("finished", 10, schema)
        assert res["mode"] == "document"
        assert res["document_id"] == 200
        assert res["line_count"] == 2


@pytest.mark.asyncio
async def test_edit_single_sale_from_form_no_lines_error():
    """edit_single_sale_from_form raises ValidationError if lines list is empty."""
    from app.core.exceptions import ValidationError
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    with patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_before:
        mock_before.return_value = {"id": 10, "client_id": 5}

        cmd = SalesCommands(session)
        schema = SaleFormSchema(client_id=5, notes="", lines=[])

        with pytest.raises(ValidationError):
            await cmd.edit_single_sale_from_form("finished", 10, schema)


# ── sales/queries.py (83% → target ~95%) ────────────────────────────


@pytest.mark.asyncio
async def test_get_sale_document_context_not_found():
    """get_sale_document_context returns None if document does not exist."""
    from app.modules.sales.queries import SalesQueries

    session = AsyncMock()

    with patch("app.modules.sales.repository.SaleDocumentRepository.get_by_id", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        queries = SalesQueries(session)
        res = await queries.get_sale_document_context(999)
        assert res is None
