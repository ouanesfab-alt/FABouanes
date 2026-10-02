from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.modules.clients.service import ClientService
from app.modules.sales.commands import normalize_sale_type
from app.modules.sales.schemas_validation import SaleFormSchema
from app.services.contact_directory_service import delete_supplier_by_id


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


@pytest.mark.asyncio
async def test_legacy_delete_payment_emits_event_and_invalidates_cache():
    """Legacy delete_payment_by_id in payment_service.py emits DomainEvent and invalidates cache."""
    from app.services.payment_service import delete_payment_by_id

    session = AsyncMock()
    mock_payment = MagicMock()
    mock_payment.model_dump.return_value = {"id": 123, "client_id": 10, "amount": 500.0}
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_payment
    session.execute.return_value = mock_res

    with patch("app.modules.payments.service.PaymentsService.reverse_payment_allocations", new=AsyncMock()), \
         patch("app.core.events.emit") as mock_emit, \
         patch("app.core.perf_cache.invalidate_cache_domains") as mock_inval, \
         patch("app.core.storage.mark_backup_needed"):
        ok = await delete_payment_by_id(123, db=session)

    assert ok is True
    payment_events = [c[0][0] for c in mock_emit.call_args_list if getattr(c[0][0], "entity_type", None) == "payment"]
    assert len(payment_events) == 1
    assert payment_events[0].action == "delete"
    assert payment_events[0].entity_id == 123
    mock_inval.assert_called_once_with("sales", "client", "dashboard")


@pytest.mark.asyncio
async def test_apply_raw_material_consumption_accepts_model_and_int():
    """Verify apply_raw_material_consumption resolves ID from int, dict, or object."""
    from app.services.stock_service import apply_raw_material_consumption

    session = AsyncMock()
    mock_db_mat = MagicMock()
    mock_db_mat.stock_qty = 50.0
    mock_db_mat.name = "Farine"
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_db_mat
    session.execute.return_value = mock_res

    # 1. As an ORM-like object with .id attribute (not subscriptable)
    class FakeModel:
        def __init__(self, id):
            self.id = id

    with patch("app.services.stock_service.record_stock_movement", new=AsyncMock()):
        await apply_raw_material_consumption(FakeModel(5), 10.0, "production", 1, db=session)
        # 2. As an integer directly
        await apply_raw_material_consumption(5, 5.0, "production", 1, db=session)


@pytest.mark.asyncio
async def test_apply_finished_production_accepts_model_and_int():
    """Verify apply_finished_production resolves ID from int, dict, or object."""
    from app.services.stock_service import apply_finished_production

    session = AsyncMock()
    mock_db_prod = MagicMock()
    mock_db_prod.stock_qty = 20.0
    mock_db_prod.avg_cost = 100.0
    mock_db_prod.sale_price = 150.0
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_db_prod
    session.execute.return_value = mock_res

    class FakeModel:
        def __init__(self, id):
            self.id = id

    with patch("app.services.stock_service.record_stock_movement", new=AsyncMock()):
        await apply_finished_production(FakeModel(8), 5.0, 500.0, 1, db=session)
        await apply_finished_production(8, 5.0, 500.0, 1, db=session)


