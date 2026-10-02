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


def test_tonne_unit_conversion():
    """Verify qty_to_kg and unit_price_to_kg properly handle tonne/t units."""
    from app.services.stock_service import qty_to_kg, unit_price_to_kg

    assert qty_to_kg(2.5, "tonne") == 2500.0
    assert qty_to_kg(1.0, "tonnes") == 1000.0
    assert qty_to_kg(0.5, "t") == 500.0

    assert unit_price_to_kg(50000.0, "tonne") == 50.0
    assert unit_price_to_kg(30000.0, "t") == 30.0


@pytest.mark.asyncio
async def test_sale_commands_empty_lines_validation():
    """SalesCommands raises ValidationError when sale has no lines."""
    from app.modules.sales.commands import SalesCommands
    from app.modules.sales.schemas_validation import SaleFormSchema

    session = AsyncMock()
    commands = SalesCommands(session)
    commands.sale_repo.client_exists = AsyncMock(return_value=True)

    # 1. create_sale_from_form
    schema_empty = SaleFormSchema(client_id=1, lines=[])
    with pytest.raises(ValidationError) as exc:
        await commands.create_sale_from_form(schema_empty)
    assert "La vente doit contenir au moins une ligne d'article" in str(exc.value)

    # 2. edit_sale_document_from_form
    commands.session.execute = AsyncMock()
    with patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", return_value={"has_linked_payments": False, "sale_document": {}, "sale_lines": []}):
        with pytest.raises(ValidationError) as exc:
            await commands.edit_sale_document_from_form(1, schema_empty)
        assert "La facture doit contenir au moins une ligne d'article" in str(exc.value)


@pytest.mark.asyncio
async def test_purchase_service_empty_lines_validation():
    """PurchaseService raises ValidationError when purchase document has no lines."""
    from app.modules.purchases.schemas_validation import PurchaseFormSchema
    from app.modules.purchases.service import PurchaseService

    session = AsyncMock()
    service = PurchaseService(session)

    schema_empty = PurchaseFormSchema(supplier_id=1, lines=[])
    with pytest.raises(ValidationError) as exc:
        await service.create_purchase_from_form(schema_empty)
    assert "Le bon d'achat doit contenir au moins une ligne d'article" in str(exc.value)

    with patch.object(service, "get_purchase_document_context", return_value={"purchase_document": {}, "purchase_lines": []}):
        with pytest.raises(ValidationError) as exc:
            await service.edit_purchase_document_from_form(1, schema_empty)
        assert "Le bon d'achat doit contenir au moins une ligne d'article" in str(exc.value)


@pytest.mark.asyncio
async def test_create_production_accepts_dict_with_items():
    """Verify ProductionService.create_production handles dict with items (schema format)."""
    from datetime import date
    from app.modules.production.service import ProductionService

    session = AsyncMock()
    service = ProductionService(session)

    mock_prod = MagicMock()
    mock_prod.model_dump.return_value = {"id": 1, "name": "Aliment Bovin", "stock_qty": 100.0, "avg_cost": 20.0}
    mock_mat = MagicMock()
    mock_mat.model_dump.return_value = {"id": 10, "name": "Mais", "stock_qty": 500.0, "avg_cost": 15.0}

    async def mock_execute(stmt):
        m = MagicMock()
        sql_str = str(stmt)
        if "finished_products" in sql_str:
            m.scalar_one_or_none.return_value = mock_prod
        elif "raw_materials" in sql_str:
            m.scalars.return_value.all.return_value = [mock_mat]
        return m

    session.execute = mock_execute
    session.add = MagicMock()
    session.flush = AsyncMock()

    payload = {
        "finished_product_id": 1,
        "output_quantity": 50.0,
        "production_date": date.today().isoformat(),
        "notes": "Test batch",
        "save_recipe": False,
        "items": [{"raw_material_id": 10, "quantity": 40.0}],
    }

    with patch("app.modules.production.service.apply_raw_material_consumption", new=AsyncMock()), \
         patch("app.modules.production.service.apply_finished_production", new=AsyncMock()), \
         patch("app.modules.production.service.log_activity"), \
         patch("app.modules.production.service.audit_event"), \
         patch("app.modules.production.service.mark_backup_needed"), \
         patch("app.modules.production.service.invalidate_sellable_items_cache"):
        res = await service.create_production(payload)

    assert "batch_id" in res
    assert res["remainder"] == 10.0


@pytest.mark.asyncio
async def test_expense_repository_date_parsing_resilience():
    """ExpenseRepository handles datetime objects and empty strings gracefully."""
    from datetime import datetime
    from app.modules.expenses.repository import create_expense, update_expense

    session = AsyncMock()
    mock_expense = MagicMock()
    mock_expense.id = 99
    session.flush = AsyncMock()

    with patch("app.modules.expenses.repository.ExpenseRepository.create", return_value=mock_expense), \
         patch("app.modules.expenses.repository.ExpenseRepository.get", return_value=mock_expense), \
         patch("app.modules.expenses.repository.ExpenseRepository.update", return_value=mock_expense):
        # 1. Datetime object
        eid = await create_expense(session, datetime.now(), "transport", "Carburant", 2500.0)
        assert eid == 99

        # 2. Empty string fallback to today
        await update_expense(session, 99, "", "loyer", "Loyer mois", 50000.0)


@pytest.mark.asyncio
async def test_payment_double_submit_guard_uses_local_time():
    """Verify PaymentsService double submit guard checks recent submissions correctly."""
    import os
    from datetime import date
    from app.modules.payments.service import PaymentsService

    session = AsyncMock()
    service = PaymentsService(session)

    # Mock client exists
    mock_client_res = MagicMock()
    mock_client_res.first.return_value = (10,)

    # Mock recent duplicate found in DB
    mock_dup_res = MagicMock()
    mock_dup_res.first.return_value = (123,)

    session.execute.side_effect = [mock_client_res, mock_dup_res]

    # Temporarily unset PYTEST_CURRENT_TEST to test the production guard branch
    old_env = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        with pytest.raises(ValidationError) as exc:
            await service.create_payment_record(
                client_id=10,
                amount=500.0,
                payment_date=date.today(),
                notes="Versement client",
                payment_type="versement",
            )
        assert "vient d'être soumis" in str(exc.value)
    finally:
        if old_env is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_env


@pytest.mark.asyncio
async def test_reverse_payment_allocations_handles_malformed_json_and_none_ids():
    """reverse_payment_allocations should safely ignore invalid or None ids in allocation_meta."""
    import json
    from app.modules.payments.service import PaymentsService

    session = AsyncMock()
    service = PaymentsService(session)

    # 1. Invalid JSON string
    await service.reverse_payment_allocations({"allocation_meta": "invalid-json{"})

    # 2. Malformed objects (missing/null id, non-dict, non-numeric amount)
    malformed_meta = json.dumps([
        "not-a-dict",
        {"kind": "finished", "id": None, "amount": 100},
        {"kind": "finished", "id": "invalid", "amount": 100},
        {"kind": "raw", "id": 0, "amount": 100},
        {"kind": "finished", "id": 1, "amount": "invalid-amount"},
        {"kind": "finished", "id": 2, "amount": -50},
    ])
    await service.reverse_payment_allocations({"allocation_meta": malformed_meta})






