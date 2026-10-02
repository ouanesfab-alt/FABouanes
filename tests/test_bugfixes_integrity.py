from datetime import date
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ValidationError
from app.modules.clients.service import ClientService
from app.modules.sales.schemas_validation import SaleFormSchema
from app.modules.sales.commands import normalize_sale_type
from app.services.contact_directory_service import delete_supplier_by_id, has_supplier_operations


def test_normalize_sale_type():
    """Verify normalize_sale_type supports French and English synonyms."""
    assert normalize_sale_type("comptant", 10) == "cash"
    assert normalize_sale_type("especes", 10) == "cash"
    assert normalize_sale_type("espece", 10) == "cash"
    assert normalize_sale_type("cash", 10) == "cash"
    assert normalize_sale_type("credit", 10) == "credit"
    assert normalize_sale_type("crédit", 10) == "credit"
    assert normalize_sale_type("dette", 10) == "credit"
    assert normalize_sale_type("dettes", 10) == "credit"
    assert normalize_sale_type("", 10) == "credit"
    assert normalize_sale_type("", None) == "cash"


def test_sale_form_schema_normalization():
    """Verify SaleFormSchema maps French payment types without dropping them."""
    s1 = SaleFormSchema(sale_type="comptant", lines=[])
    assert s1.sale_type == "cash"

    s2 = SaleFormSchema(sale_type="especes", lines=[])
    assert s2.sale_type == "cash"

    s3 = SaleFormSchema(sale_type="dette", lines=[])
    assert s3.sale_type == "credit"

    s4 = SaleFormSchema(sale_type="unknown_type", lines=[])
    assert s4.sale_type is None


@pytest.mark.asyncio
async def test_client_service_delete_client_blocks_linked_operations():
    """ClientService.delete_client must raise ValidationError when client has history."""
    session = AsyncMock()
    service = ClientService(session)

    mock_client = MagicMock()
    mock_client.model_dump.return_value = {"id": 42, "name": "Client Test"}
    service.repo.get_by_id = AsyncMock(return_value=mock_client)
    service.repo.has_operations = AsyncMock(return_value=True)

    with pytest.raises(ValidationError) as exc:
        await service.delete_client(42)

    assert "Impossible de supprimer ce client" in str(exc.value)


@pytest.mark.asyncio
async def test_client_service_delete_client_allows_unlinked():
    """ClientService.delete_client succeeds when client has no operations."""
    session = AsyncMock()
    service = ClientService(session)

    mock_client = MagicMock()
    mock_client.model_dump.return_value = {"id": 42, "name": "Client Test"}
    service.repo.get_by_id = AsyncMock(return_value=mock_client)
    service.repo.has_operations = AsyncMock(return_value=False)
    service.repo.delete = AsyncMock(return_value=True)

    with patch("app.modules.clients.service.invalidate_client_cache"), \
         patch("app.modules.clients.service.emit"):
        success = await service.delete_client(42)

    assert success is True


@pytest.mark.asyncio
async def test_supplier_deletion_blocks_linked_purchases():
    """Supplier deletion raises ValidationError when supplier has purchases."""
    session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 3  # 3 purchases
    session.execute.return_value = mock_res

    with pytest.raises(ValidationError) as exc:
        await delete_supplier_by_id(99, db=session)

    assert "Impossible de supprimer ce fournisseur" in str(exc.value)


@pytest.mark.asyncio
async def test_assistant_tool_actions_contacts_handles_delete_client_validation_error():
    """Sabrina assistant delete_client tool returns user-friendly error on ValidationError."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.clients.service.ClientService.delete_client", side_effect=ValidationError("Client a des opérations")):
        res = await handle_contacts("delete_client", {"client_id": 10}, session_maker)

    assert res == {"error": "Client a des opérations"}
