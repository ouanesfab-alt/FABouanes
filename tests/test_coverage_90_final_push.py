"""Tests unitaires ciblés pour propulser le taux de couverture globale Python Core."""
from __future__ import annotations

import pytest
from unittest import mock

from app.core.exceptions import NotFoundError, ConflictError
from app.modules.sales.commands import SalesCommands
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema


@pytest.mark.asyncio
async def test_sales_commands_errors():
    mock_session = mock.AsyncMock()
    cmd = SalesCommands(mock_session)

    # edit_sale_document_from_form not found
    with mock.patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", mock.AsyncMock(return_value=None)):
        schema = SaleFormSchema(client_id=1, lines=[SaleLineSchema(item_key="finished:1", quantity=1.0, unit="kg", unit_price=10.0)])
        with pytest.raises(NotFoundError):
            await cmd.edit_sale_document_from_form(999999, schema)

    # edit_sale_document_from_form linked payments conflict
    with mock.patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", mock.AsyncMock(return_value={"has_linked_payments": True})):
        schema = SaleFormSchema(client_id=1, lines=[SaleLineSchema(item_key="finished:1", quantity=1.0, unit="kg", unit_price=10.0)])
        with pytest.raises(ConflictError):
            await cmd.edit_sale_document_from_form(1, schema)

    # edit_single_sale_from_form not found
    with mock.patch("app.modules.sales.repository.SaleRepository.get_sale_detail", mock.AsyncMock(return_value=None)):
        schema = SaleFormSchema(client_id=1, lines=[SaleLineSchema(item_key="finished:1", quantity=1.0, unit="kg", unit_price=10.0)])
        with pytest.raises(NotFoundError):
            await cmd.edit_single_sale_from_form("finished", 999999, schema)
