from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.exceptions import ValidationError
from app.modules.purchases.service import PurchaseService
from app.modules.purchases.schemas_validation import PurchaseFormSchema, PurchaseLineSchema
from app.core.models import Purchase, PurchaseDocument
from pydantic import ValidationError as PydanticValidationError


# ---------------------------------------------------------------------------
# PurchaseFormSchema & PurchaseLineSchema validation
# ---------------------------------------------------------------------------

def test_purchase_line_schema_invalid_id() -> None:
    with pytest.raises((PydanticValidationError, ValueError)):
        PurchaseLineSchema(raw_material_id="invalid", quantity=5.0, unit="kg", unit_price=100.0)


def test_purchase_line_schema_valid_raw() -> None:
    line = PurchaseLineSchema(raw_material_id="raw:3", quantity=5.0, unit="kg", unit_price=100.0)
    assert line.raw_material_id == "raw:3"
    assert line.quantity == 5.0


def test_purchase_form_schema_empty() -> None:
    # Empty lines should be fine at schema level (defaults to empty list)
    schema = PurchaseFormSchema(supplier_id=1, notes="Test")
    assert len(schema.lines) == 0


# ---------------------------------------------------------------------------
# PurchaseService mocks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purchase_form_context() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    session.execute.return_value = mock_result
    
    service = PurchaseService(session)
    service.purchase_repo = AsyncMock()
    service.purchase_repo.list_raw_material_choices.return_value = []
    
    with patch("app.modules.purchases.service.unit_choices", return_value=["kg", "qt"]):
        result = await service.purchase_form_context()
        assert "units" in result
        assert result["units"] == ["kg", "qt"]



@pytest.mark.asyncio
async def test_get_purchase_document_context_not_found() -> None:
    session = AsyncMock()
    service = PurchaseService(session)
    service.doc_repo = AsyncMock()
    service.doc_repo.get_by_id.return_value = None

    result = await service.get_purchase_document_context(999)
    assert result is None


@pytest.mark.asyncio
async def test_get_purchase_document_context_success() -> None:
    session = AsyncMock()
    service = PurchaseService(session)
    service.doc_repo = MagicMock()
    
    doc = {"id": 1, "supplier_id": 2, "total": 5000}
    lines = [{"id": 10, "document_id": 1}]
    
    service.doc_repo.get_by_id = AsyncMock(return_value=doc)
    service.doc_repo.list_lines = AsyncMock(return_value=lines)

    result = await service.get_purchase_document_context(1)
    assert result is not None
    assert result["purchase_document"] == doc
    assert result["purchase_lines"] == lines


@pytest.mark.asyncio
async def test_delete_purchase_success() -> None:
    session = AsyncMock()
    service = PurchaseService(session)
    service.purchase_repo = AsyncMock()
    
    purchase = {"id": 5, "total": 1000}
    service.purchase_repo.get_by_id.return_value = purchase
    
    with patch.object(service, "reverse_purchase", new_callable=AsyncMock, return_value=True) as mock_reverse, \
         patch("app.modules.purchases.service.emit") as mock_emit:
        result = await service.delete_purchase_by_id(5)
        assert result is True
        mock_reverse.assert_awaited_once_with(5)
        mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_purchase_reverse_fails() -> None:
    session = AsyncMock()
    service = PurchaseService(session)
    service.purchase_repo = AsyncMock()
    
    purchase = {"id": 5, "total": 1000}
    service.purchase_repo.get_by_id.return_value = purchase
    
    with patch.object(service, "reverse_purchase", new_callable=AsyncMock, return_value=False) as mock_reverse:
        result = await service.delete_purchase_by_id(5)
        assert result is False
        mock_reverse.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_get_purchase_edit_context_not_found() -> None:
    session = AsyncMock()
    service = PurchaseService(session)
    service.purchase_repo = AsyncMock()
    service.purchase_repo.get_by_id.return_value = None

    result = await service.get_purchase_edit_context(999)
    assert result is None
