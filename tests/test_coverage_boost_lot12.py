"""Tests de couverture ciblés — Lot 12.

Couvre: modules/sales/commands.py (edit_sale_document_from_form validation checks & error handling)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.exceptions import NotFoundError, ConflictError
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema


# ── sales/commands.py (81% → target ~90%) ───────────────────────────


@pytest.mark.asyncio
async def test_edit_sale_document_not_found():
    """edit_sale_document_from_form raises NotFoundError if document missing."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    with patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", new_callable=AsyncMock) as mock_ctx:
        mock_ctx.return_value = None

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=1,
            notes="",
            lines=[SaleLineSchema(item_key="finished:1", quantity=2.0, unit="kg", unit_price=100.0)]
        )

        with pytest.raises(NotFoundError):
            await cmd.edit_sale_document_from_form(999, schema)


@pytest.mark.asyncio
async def test_edit_sale_document_has_linked_payments():
    """edit_sale_document_from_form raises ConflictError if document has linked payments."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    context = {
        "sale_document": MagicMock(),
        "sale_lines": [],
        "has_linked_payments": True,
    }

    with patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", new_callable=AsyncMock) as mock_ctx:
        mock_ctx.return_value = context

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=1,
            notes="",
            lines=[SaleLineSchema(item_key="finished:1", quantity=2.0, unit="kg", unit_price=100.0)]
        )

        with pytest.raises(ConflictError):
            await cmd.edit_sale_document_from_form(10, schema)


@pytest.mark.asyncio
async def test_edit_single_sale_not_found():
    """edit_single_sale_from_form raises NotFoundError if sale missing."""
    from app.modules.sales.commands import SalesCommands

    session = AsyncMock()

    with patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_detail:
        mock_detail.return_value = None

        cmd = SalesCommands(session)
        schema = SaleFormSchema(
            client_id=1,
            notes="",
            lines=[SaleLineSchema(item_key="finished:1", quantity=2.0, unit="kg", unit_price=100.0)]
        )

        with pytest.raises(NotFoundError):
            await cmd.edit_single_sale_from_form("finished", 999, schema)
