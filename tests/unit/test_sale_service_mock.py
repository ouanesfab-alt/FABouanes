from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.exceptions import ValidationError
from app.modules.sales.service import SalesService
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
from app.core.models import Sale, SaleDocument
from pydantic import ValidationError as PydanticValidationError


# ---------------------------------------------------------------------------
# SaleFormSchema & SaleLineSchema validation
# ---------------------------------------------------------------------------

def test_sale_line_schema_invalid_id() -> None:
    with pytest.raises((PydanticValidationError, ValueError)):
        SaleLineSchema(item_key="invalid", quantity=5.0, unit="kg", unit_price=100.0)


def test_sale_line_schema_valid_finished() -> None:
    line = SaleLineSchema(item_key="finished:7", quantity=5.0, unit="kg", unit_price=100.0)
    assert line.item_key == "finished:7"
    assert line.quantity == 5.0


def test_sale_form_schema_empty() -> None:
    # Empty lines should be fine at schema level (defaults to empty list)
    schema = SaleFormSchema(client_id=1, notes="Test")
    assert len(schema.lines) == 0


# ---------------------------------------------------------------------------
# SalesService mocks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sale_form_context() -> None:
    session = AsyncMock()
    service = SalesService(session)
    service.sale_repo = AsyncMock()
    service.sale_repo.list_sellable_item_choices.return_value = []
    
    with patch("app.modules.sales.service.unit_choices", return_value=["kg", "qt"]):
        result = await service.sale_form_context()
        assert "units" in result
        assert result["units"] == ["kg", "qt"]


@pytest.mark.asyncio
async def test_get_sale_document_context_not_found() -> None:
    session = AsyncMock()
    service = SalesService(session)
    service.doc_repo = AsyncMock()
    service.doc_repo.get_by_id.return_value = None

    result = await service.get_sale_document_context(999)
    assert result is None


@pytest.mark.asyncio
async def test_get_sale_document_context_success() -> None:
    session = MagicMock()
    service = SalesService(session)
    service.doc_repo = MagicMock()
    
    doc = MagicMock()
    doc.id = 1
    doc.client_id = 2
    doc.total = 5000
    doc_dict = {"id": 1, "client_id": 2, "total": 5000}
    doc.model_dump.return_value = doc_dict
    
    lines = [{"row_id": 10, "row_kind": "finished", "document_id": 1}]
    
    service.doc_repo.get_by_id = AsyncMock(return_value=doc)
    service.doc_repo.list_lines = AsyncMock(return_value=lines)
    service.doc_repo.document_has_linked_payments = AsyncMock(return_value=False)

    result = await service.get_sale_document_context(1)
    assert result is not None
    assert result["sale_document"] == doc_dict
    assert result["sale_lines"] == lines
    assert result["has_linked_payments"] is False


@pytest.mark.asyncio
async def test_delete_sale_success() -> None:
    session = AsyncMock()
    service = SalesService(session)
    service.sale_repo = AsyncMock()
    
    sale = {"id": 5, "total": 1000, "client_id": 1}
    service.sale_repo.get_sale_detail.return_value = sale
    
    with patch.object(service, "reverse_sale", new_callable=AsyncMock, return_value=True) as mock_reverse, \
         patch("app.modules.sales.service.emit") as mock_emit:
        result = await service.delete_sale_by_id("finished", 5)
        assert result is True
        mock_reverse.assert_awaited_once_with("finished", 5)
        mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_sale_reverse_fails() -> None:
    session = AsyncMock()
    service = SalesService(session)
    service.sale_repo = AsyncMock()
    
    sale = {"id": 5, "total": 1000, "client_id": 1}
    service.sale_repo.get_sale_detail.return_value = sale
    
    with patch.object(service, "reverse_sale", new_callable=AsyncMock, return_value=False) as mock_reverse:
        result = await service.delete_sale_by_id("finished", 5)
        assert result is False
        mock_reverse.assert_awaited_once_with("finished", 5)


@pytest.mark.asyncio
async def test_get_sale_edit_context_not_found() -> None:
    session = AsyncMock()
    service = SalesService(session)
    service.sale_repo = AsyncMock()
    service.sale_repo.get_sale_detail.return_value = None

    result = await service.get_sale_edit_context("finished", 999)
    assert result is None
