# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
import datetime

from app.modules.assistant.tool_actions import execute_tool_action
from app.modules.assistant.tool_actions_insights import handle_insights
from app.modules.assistant.tool_actions_catalog import handle_catalog
from app.modules.assistant.tool_actions_contacts import handle_contacts
from app.modules.assistant.tool_actions_production import handle_production
from app.modules.assistant.tool_actions_tools import handle_tools
from app.modules.assistant.tool_actions_admin import handle_admin
from app.modules.assistant.tool_actions_operations import handle_operations


# =============================================================================
# Simple dummy class for database models to bypass type/mock strict validation
# =============================================================================
class DummyModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# =============================================================================
# Helper function to generate mock session maker
# =============================================================================
def get_mock_session_maker(session_mock):
    # Mock session.begin() to support async with context manager
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=None)
    session_mock.begin = MagicMock(return_value=mock_begin)

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=session_mock)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=fake_cm)


# =============================================================================
# 1. Tests for tool_actions_insights.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_insights():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    
    # Mock async_cached_result to bypass caching issues in test runs
    async def mock_async_cached_result(key, builder, ttl_seconds=None):
        return await builder()

    with patch("app.core.perf_cache.async_cached_result", side_effect=mock_async_cached_result):
        # 1. get_business_insights (top_debtors)
        mock_res = MagicMock()
        mock_res.fetchall.return_value = [("Jean", "0555", Decimal("15000.0"))]
        mock_session.execute.return_value = mock_res
        
        session_maker = get_mock_session_maker(mock_session)
        res = await handle_insights("get_business_insights", {"insight_type": "top_debtors"}, session_maker)
        assert res is not None
        assert "top_debtors" in res
        assert res["top_debtors"][0]["name"] == "Jean"

        # 2. get_business_insights (monthly_sales_comparison)
        mock_session.execute.reset_mock()
        mock_scalar = MagicMock()
        mock_scalar.scalar.side_effect = [Decimal("50000.0"), Decimal("40000.0")]
        mock_session.execute.return_value = mock_scalar
        
        res = await handle_insights("get_business_insights", {"insight_type": "monthly_sales_comparison"}, session_maker)
        assert res is not None
        assert res["growth_rate"] == 25.0

        # 3. get_current_weather
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "Paris: 20C"
            mock_get.return_value = mock_resp
            
            res = await handle_insights("get_current_weather", {"location": "Paris"}, session_maker)
            assert res is not None
            assert "weather" in res
            assert res["weather"] == "Paris: 20C"

        # 4. search_web
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<div class="result results_links results_links_deep web-result "><a class="result__a" href="http://test.com">Test Title</a><div class="result__snippet">Snippet info</div>'
            mock_get.return_value = mock_resp
            
            res = await handle_insights("search_web", {"query": "test query"}, session_maker)
            assert res is not None
            assert "results" in res
            assert len(res["results"]) > 0
            assert res["results"][0]["title"] == "Test Title"


# =============================================================================
# 2. Tests for tool_actions_catalog.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_catalog():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)
    
    # Mock async_cached_result to bypass caching issues in test runs
    async def mock_async_cached_result(key, builder, ttl_seconds=None):
        return await builder()

    # 1. add_product (finished)
    mock_prod = DummyModel(id=99, name="Aliment Mouton")
    mock_catalog_service = MagicMock()
    mock_catalog_service.create_finished_product = AsyncMock(return_value=mock_prod)
    
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("add_product", {
            "name": "Aliment Mouton", "category": "finished", "price": "1400.0", "cost": "1000.0", "unit": "sac", "stock_qty": "10"
        }, session_maker)
        assert res["success"] is True
        assert res["product_id"] == 99

    # 2. add_product (raw)
    mock_raw = DummyModel(id=101, name="Orge")
    mock_catalog_service.create_raw_material = AsyncMock(return_value=mock_raw)
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("add_product", {
            "name": "Orge", "category": "raw", "price": "0", "cost": "85.0", "unit": "kg", "stock_qty": "5000", "alert_threshold": "1000"
        }, session_maker)
        assert res["success"] is True
        assert res["product_id"] == 101

    # 3. modify_product (finished)
    mock_catalog_service.get_product = AsyncMock(return_value=DummyModel(name="Aliment Mouton", default_unit="sac", stock_qty=10.0, sale_price=1400.0, avg_cost=1000.0))
    mock_catalog_service.update_finished_product = AsyncMock(return_value=True)
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("modify_product", {
            "product_id": 99, "category": "finished", "price": "1500.0"
        }, session_maker)
        assert res["success"] is True

    # 4. modify_product (raw)
    mock_catalog_service.get_raw_material = AsyncMock(return_value=DummyModel(name="Orge", unit="kg", stock_qty=5000.0, sale_price=0.0, avg_cost=85.0, alert_threshold=1000.0))
    mock_catalog_service.update_raw_material = AsyncMock(return_value=True)
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("modify_product", {
            "product_id": 101, "category": "raw", "cost": "88.0"
        }, session_maker)
        assert res["success"] is True

    # 5. delete_product (finished)
    mock_catalog_service.delete_finished_product = AsyncMock(return_value=True)
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("delete_product", {
            "product_id": 99, "category": "finished"
        }, session_maker)
        assert res["success"] is True

    # 6. delete_product (raw)
    mock_catalog_service.delete_raw_material = AsyncMock(return_value=True)
    with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
        res = await handle_catalog("delete_product", {
            "product_id": 101, "category": "raw"
        }, session_maker)
        assert res["success"] is True

    # 7. search_products
    mock_session.execute = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchall.side_effect = [
        [(99, "Aliment Mouton", Decimal("1400.0"), Decimal("1000.0"), "sac", Decimal("10.0"))],
        [(101, "Orge", Decimal("85.0"), "kg", Decimal("5000.0"))]
    ]
    mock_session.execute.return_value = mock_res
    with patch("app.core.perf_cache.async_cached_result", side_effect=mock_async_cached_result):
        res = await handle_catalog("search_products", {"query": "mouton"}, session_maker)
        assert "results" in res
        assert len(res["results"]) == 2

    # 8. import_bulk_products_excel
    with patch("app.modules.assistant.tool_actions_catalog._assert_workspace_path"):
        with patch("app.services.excel_import_service.parse_excel_bulk_products", return_value=[{"name": "Orge", "unit": "kg", "stock_qty": 5000, "avg_cost": 85, "sale_price": 0, "alert_threshold": 1000}]):
            mock_catalog_service.create_raw_material = AsyncMock()
            with patch("app.modules.catalog.application.services.CatalogService", return_value=mock_catalog_service):
                res = await handle_catalog("import_bulk_products_excel", {"filepath": "products.xlsx", "is_raw_material": True}, session_maker)
                assert res["success"] is True

    # 9. get_enum_values
    with patch("app.modules.assistant.business_helpers.get_enum_values", return_value=["val1", "val2"]):
        res = await handle_catalog("get_enum_values", {"table": "clients", "column": "category"}, session_maker)
        assert res == ["val1", "val2"]


# =============================================================================
# 3. Tests for tool_actions_contacts.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_contacts():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)
    
    # 1. add_client
    mock_cli = DummyModel(id=42)
    mock_client_service = MagicMock()
    mock_client_service.create_client = AsyncMock(return_value=mock_cli)
    with patch("app.modules.clients.application.services.ClientService", return_value=mock_client_service):
        res = await handle_contacts("add_client", {
            "name": "Massi", "phone": "0555123456", "opening_credit": "5000.0"
        }, session_maker)
        assert res["success"] is True
        assert res["client_id"] == 42

    # 2. modify_client
    mock_client_service.get_client = AsyncMock(return_value=DummyModel(name="Massi"))
    mock_client_service.update_client = AsyncMock(return_value=True)
    with patch("app.modules.clients.application.services.ClientService", return_value=mock_client_service):
        res = await handle_contacts("modify_client", {
            "client_id": 42, "phone": "0555654321"
        }, session_maker)
        assert res["success"] is True

    # 3. delete_client
    mock_client_service.delete_client = AsyncMock(return_value=True)
    with patch("app.modules.clients.application.services.ClientService", return_value=mock_client_service):
        res = await handle_contacts("delete_client", {"client_id": 42}, session_maker)
        assert res["success"] is True

    # 4. add_supplier
    with patch("app.services.contact_directory_service.create_supplier_from_form", new_callable=AsyncMock, return_value=12):
        res = await handle_contacts("add_supplier", {
            "name": "Somacob", "phone": "034211111", "address": "Bejaia"
        }, session_maker)
        assert res["success"] is True
        assert res["supplier_id"] == 12

    # 5. modify_supplier
    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock, return_value={"name": "Somacob", "phone": "034211111"}):
        with patch("app.services.contact_directory_service.update_supplier_from_form", new_callable=AsyncMock, return_value=True):
            res = await handle_contacts("modify_supplier", {
                "supplier_id": 12, "notes": "New note"
            }, session_maker)
            assert res["success"] is True

    # 6. delete_supplier
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))
    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock, return_value={"id": 12}):
        with patch("app.services.contact_directory_service.delete_supplier_by_id", new_callable=AsyncMock, return_value=True):
            res = await handle_contacts("delete_supplier", {"supplier_id": 12}, session_maker)
            assert res["success"] is True


# =============================================================================
# 4. Tests for tool_actions_production.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_production():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)

    # 1. create_recipe
    with patch("app.services.recipe_service.save_recipe_definition", new_callable=AsyncMock, return_value=5):
        res = await handle_production("create_recipe", {
            "name": "Recipe 1", "finished_product_id": 1, "items": [{"raw_material_id": 2, "quantity": "100.0"}]
        }, session_maker)
        assert res["success"] is True
        assert res["recipe_id"] == 5

    # 2. delete_recipe
    mock_session.execute = AsyncMock()
    res = await handle_production("delete_recipe", {"recipe_id": 5}, session_maker)
    assert res["success"] is True

    # 3. add_production_batch
    db_product = DummyModel(id=1, name="Finished Product")
    db_recipe = DummyModel(id=10, finished_product_id=1)
    db_recipe_item = DummyModel(id=100, recipe_id=10, raw_material_id=2, quantity=Decimal("0.5"))
    db_material = DummyModel(id=2, name="Raw Material", avg_cost=Decimal("120.0"))

    # Mock DB query results for FinishedProduct, SavedRecipe, SavedRecipeItem, RawMaterial
    class MockResult:
        def __init__(self, val):
            self.val = val
        def scalar_one_or_none(self):
            return self.val
        def scalars(self):
            class Scaler:
                def __init__(self, items):
                    self.items = items
                def all(self):
                    return self.items
            return Scaler(self.val)

    async def mock_execute(query, *args, **kwargs):
        q_str = str(query).lower()
        if "finished_product" in q_str or "finishedproduct" in q_str:
            return MockResult(db_product)
        elif "saved_recipe_item" in q_str or "savedrecipeitem" in q_str:
            return MockResult([db_recipe_item])
        elif "saved_recipe" in q_str or "savedrecipe" in q_str:
            return MockResult(db_recipe)
        elif "raw_material" in q_str or "rawmaterial" in q_str:
            return MockResult(db_material)
        return MockResult(None)

    mock_session.execute = mock_execute
    
    # Mock stock service calls
    with patch("app.services.stock_service.apply_raw_material_consumption", new_callable=AsyncMock) as mock_consume:
        with patch("app.services.stock_service.apply_finished_production", new_callable=AsyncMock) as mock_produce:
            res = await handle_production("add_production_batch", {
                "finished_product_id": 1, "quantity": "100.0"
            }, session_maker)
            assert res is not None
            assert res.get("success") is True
            assert "batch_id" in res
            mock_consume.assert_called()
            mock_produce.assert_called()


# =============================================================================
# 5. Tests for tool_actions_tools.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_tools():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)

    # 1. list_user_notes
    with patch("app.utils.tool_pages.list_user_notes", return_value=[{"id": "note1"}]):
        res = await handle_tools("list_user_notes", {}, session_maker)
        assert "notes" in res

    # 2. get_user_note
    with patch("app.utils.tool_pages.get_user_note", return_value={"id": "note1", "title": "T"}) as mock_get:
        res = await handle_tools("get_user_note", {"note_id": "note1"}, session_maker)
        assert res["note"]["title"] == "T"
        mock_get.assert_called_once_with("note1")

    # 3. create_user_note
    with patch("app.utils.tool_pages.create_user_note", return_value={"id": "note1", "title": "T"}):
        res = await handle_tools("create_user_note", {"title": "T"}, session_maker)
        assert res["note"]["title"] == "T"

    # 4. save_user_note
    with patch("app.utils.tool_pages.save_user_note", return_value={"id": "note1", "title": "T"}) as mock_save:
        res = await handle_tools("save_user_note", {"note_id": "note1", "title": "T", "content": "C"}, session_maker)
        assert res["note"]["title"] == "T"
        mock_save.assert_called_once()

    # 5. delete_user_note
    with patch("app.utils.tool_pages.delete_user_note", return_value=True):
        res = await handle_tools("delete_user_note", {"note_id": "note1"}, session_maker)
        assert res["success"] is True

    # 6. remember
    with patch("app.modules.assistant.memory.remember", return_value={"success": True}) as mock_remember:
        res = await handle_tools("remember", {"content": "T", "category": "general"}, session_maker)
        assert res["success"] is True
        mock_remember.assert_called_once_with("T", category="general", source="user_explicit")

    # 7. recall
    with patch("app.modules.assistant.memory.recall", return_value=[]) as mock_recall:
        res = await handle_tools("recall", {"query": "T"}, session_maker)
        assert res == []
        mock_recall.assert_called_once_with("T", limit=10)

    # 8. forget
    with patch("app.modules.assistant.memory.forget", return_value=True) as mock_forget:
        res = await handle_tools("forget", {"memory_id": "10"}, session_maker)
        assert res is True
        mock_forget.assert_called_once_with(10)

    # 9. list_bon_space_documents
    with patch("app.services.bon_space_service.list_bon_space_documents", new_callable=AsyncMock, return_value=[{"id": 1, "search_text": "S"}]) as mock_list_docs:
        res = await handle_tools("list_bon_space_documents", {"query": "S", "kind": "pdf"}, session_maker)
        assert "documents" in res
        assert "search_text" not in res["documents"][0]
        mock_list_docs.assert_called_once_with(q="S", kind="pdf", limit=80)

    # 10. get_recent_activity_logs
    with patch("app.services.activity_service.list_admin_activity", new_callable=AsyncMock, return_value=[{"sentence": "Act"}]) as mock_logs:
        res = await handle_tools("get_recent_activity_logs", {}, session_maker)
        assert res["logs"] == ["Act"]
        mock_logs.assert_called_once()

    # 11. get_active_alerts
    raw_material_alert = DummyModel(name="Orge", stock_qty=100.0, alert_threshold=200.0, unit="kg")
    finished_product_alert = DummyModel(name="Aliment", stock_qty=50.0, alert_threshold=100.0, default_unit="sac")
    
    # Mock SQL Results
    class MockResult:
        def __init__(self, val):
            self.val = val
        def all(self):
            return self.val

    async def mock_execute(query, *args, **kwargs):
        q_str = str(query).lower()
        if "raw_materials" in q_str:
            return MockResult([raw_material_alert])
        elif "finished_products" in q_str:
            return MockResult([finished_product_alert])
        return MockResult([])

    mock_session.execute = mock_execute
    with patch("app.services.alert_service.check_overdue_clients", new_callable=AsyncMock, return_value=[{"name": "Jean", "jours_inactif": 45, "balance": 15000}]):
        res = await handle_tools("get_active_alerts", {}, session_maker)
        assert "alerts" in res
        assert len(res["alerts"]) == 3

    # 12. redirect_to
    res = await handle_tools("redirect_to", {"url": "/clients"}, session_maker)
    assert res == {"redirect_url": "/clients"}

    # 13. change_theme
    res = await handle_tools("change_theme", {"theme": "dark"}, session_maker)
    assert res == {"theme": "dark"}


# =============================================================================
# 6. Tests for tool_actions_admin.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_admin():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)

    # 1. create_app_backup
    with patch("app.services.admin_service.create_manual_backup", new_callable=AsyncMock, return_value={"ok": True, "local_path": "b.sql"}):
        res = await handle_admin("create_app_backup", {}, session_maker, user_role="admin")
        assert res["success"] is True

    # 2. list_app_backups
    with patch("app.services.admin_service.list_restore_backups", return_value=[{"id": 1}]):
        res = await handle_admin("list_app_backups", {}, session_maker, user_role="admin")
        assert "backups" in res
        assert len(res["backups"]) == 1

    # 3. update_app_user
    with patch("app.services.admin_service.update_user_account", new_callable=AsyncMock) as mock_upd:
        res = await handle_admin("update_app_user", {
            "user_id": 1, "role": "admin", "is_active": True
        }, session_maker, user_role="admin")
        assert res["success"] is True
        mock_upd.assert_called_once()

    # 4. restore_app_backup
    with patch("app.services.admin_service.restore_backup_by_value", new_callable=AsyncMock) as mock_restore:
        res = await handle_admin("restore_app_backup", {"backup_name": "b.sql"}, session_maker, user_role="admin")
        assert res["success"] is True
        mock_restore.assert_called_once_with("b.sql")

    # 5. create_app_user
    with patch("app.services.admin_service.create_user_account", new_callable=AsyncMock, return_value={"ok": True, "message": "OK"}) as mock_create:
        res = await handle_admin("create_app_user", {"username": "user", "password": "pwd", "role": "operator"}, session_maker, user_role="admin")
        assert res["success"] is True
        mock_create.assert_called_once_with("user", "pwd", "operator")

    # 6. change_app_user_password
    with patch("app.core.security.validate_password_strength", return_value=(True, "")):
        with patch("app.services.auth_service.get_user_by_username", new_callable=AsyncMock, return_value={"id": 1, "username": "user"}):
            with patch("app.modules.users.repository.update_password", new_callable=AsyncMock) as mock_upd_pwd:
                res = await handle_admin("change_app_user_password", {"username": "user", "new_password": "pwd"}, session_maker, user_role="admin")
                assert res["success"] is True
                mock_upd_pwd.assert_called_once()

    # 7. delete_app_user
    with patch("app.services.auth_service.get_user_by_username", new_callable=AsyncMock, return_value={"id": 1, "username": "user"}):
        mock_session.execute = AsyncMock()
        res = await handle_admin("delete_app_user", {"username": "user"}, session_maker, user_role="admin")
        assert res["success"] is True

    # 8. update_setting
    with patch("app.core.db_helpers.db_manager.set_setting") as mock_set:
        res = await handle_admin("update_setting", {"key": "k", "value": "v"}, session_maker, user_role="admin")
        assert res["success"] is True
        mock_set.assert_called_once_with("k", "v")

    # 9. run_system_maintenance
    with patch("app.services.admin_service.run_database_maintenance", return_value={"ok": True, "message": "Done"}):
        res = await handle_admin("run_system_maintenance", {}, session_maker, user_role="admin")
        assert res["success"] is True

    # 10. save_backup_settings
    with patch("app.services.backup_service.save_backup_configuration", new_callable=AsyncMock) as mock_save_config:
        res = await handle_admin("save_backup_settings", {
            "gdrive_backup_dir": "dir", "backup_snapshot_time": "03:00", "backup_local_retention": 15
        }, session_maker, user_role="admin")
        assert res["success"] is True
        mock_save_config.assert_called_once()

    # 11. read_app_file & modify_app_file
    with patch("app.modules.assistant.tool_actions_admin._assert_workspace_path"):
        with patch("builtins.open", mock_open := MagicMock()):
            mock_open.return_value.__enter__.return_value.read.return_value = "file content text"
            
            res = await handle_admin("read_app_file", {"filepath": "app/core/config.py"}, session_maker, user_role="admin")
            assert res == {"content": "file content text"}

            res = await handle_admin("modify_app_file", {
                "filepath": "app/core/config.py", "old_content": "text", "new_content": "replacement"
            }, session_maker, user_role="admin")
            assert res["success"] is True


# =============================================================================
# 7. Tests for tool_actions_operations.py
# =============================================================================
@pytest.mark.asyncio
async def test_handle_operations():
    mock_session = AsyncMock()
    session_maker = get_mock_session_maker(mock_session)

    # 1. add_sale
    with patch("app.modules.sales.application.services.SalesService.create_sale_from_form", new_callable=AsyncMock, return_value={"sale_id": 50}) as mock_create_sale:
        with patch("app.modules.payments.application.services.PaymentsService.create_payment_from_form", new_callable=AsyncMock) as mock_create_pay:
            res = await handle_operations("add_sale", {
                "client_id": 1, "finished_product_id": 2, "quantity": "10", "unit_price": "1400", "amount_paid": "5000"
            }, session_maker)
            assert res["success"] is True
            assert res["sale_id"] == 50
            mock_create_sale.assert_called_once()
            mock_create_pay.assert_called_once()

    # 2. add_purchase
    with patch("app.modules.purchases.application.services.PurchaseService.create_purchase_from_form", new_callable=AsyncMock, return_value={"purchase_id": 60}) as mock_create_purchase:
        res = await handle_operations("add_purchase", {
            "supplier_id": 3, "raw_material_id": 4, "quantity": "20", "unit_price": "900"
        }, session_maker)
        assert res["success"] is True
        assert res["purchase_id"] == 60
        mock_create_purchase.assert_called_once()

    # 3. add_payment
    with patch("app.modules.payments.application.services.PaymentsService.create_payment_from_form", new_callable=AsyncMock, return_value=(70, "Avance")) as mock_create_payment:
        res = await handle_operations("add_payment", {
            "client_id": 1, "amount": "10000", "payment_type": "avance"
        }, session_maker)
        assert res["success"] is True
        assert res["payment_id"] == 70
        mock_create_payment.assert_called_once()

    # 4. delete_operation (sale)
    with patch("app.modules.sales.application.services.SalesService.delete_sale_by_id", new_callable=AsyncMock, return_value=True) as mock_del_sale:
        res = await handle_operations("delete_operation", {
            "tx_kind": "sale_finished", "tx_id": 50
        }, session_maker)
        assert res["success"] is True
        mock_del_sale.assert_called_once_with("finished", 50)

    # 5. add_expense
    with patch("app.modules.expenses.application.services.ExpensesService.add_expense", new_callable=AsyncMock, return_value=80) as mock_add_exp:
        res = await handle_operations("add_expense", {
            "category": "salaires", "amount": "12000", "description": "Pay", "payment_method": "ccp"
        }, session_maker)
        assert res["success"] is True
        assert res["expense_id"] == 80
        mock_add_exp.assert_called_once()

    # 6. modify_expense
    db_expense = DummyModel(id=80, date=datetime.date.today(), category="transport", amount=Decimal("3000"), description="Logistics", payment_method="cash")
    with patch("app.modules.expenses.application.services.ExpensesService.get_expense", new_callable=AsyncMock, return_value=db_expense):
        with patch("app.modules.expenses.application.services.ExpensesService.modify_expense", new_callable=AsyncMock) as mock_mod_exp:
            res = await handle_operations("modify_expense", {
                "expense_id": 80, "amount": "3500"
            }, session_maker)
            assert res["success"] is True
            mock_mod_exp.assert_called_once()

    # 7. delete_expense
    with patch("app.modules.expenses.application.services.ExpensesService.remove_expense", new_callable=AsyncMock, return_value=True) as mock_rem_exp:
        res = await handle_operations("delete_expense", {
            "expense_id": 80
        }, session_maker)
        assert res["success"] is True
        mock_rem_exp.assert_called_once()

    # 8. add_supplier_payment
    mock_session.execute = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchone.side_effect = [(3,), (90,)]  # Supplier exists check, and RETURNING id
    mock_session.execute.return_value = mock_res
    res = await handle_operations("add_supplier_payment", {
        "supplier_id": 3, "amount": "15000", "notes": "Acompte orge"
    }, session_maker)
    assert res["success"] is True
    assert res["payment_id"] == 90

    # 9. get_print_link
    res = await handle_operations("get_print_link", {
        "doc_type": "sale_finished", "item_id": 50
    }, session_maker)
    assert "print_url" in res
    assert res["print_url"] == "/print/sale_finished/50"

    # 10. get_export_link
    res = await handle_operations("get_export_link", {
        "export_type": "clients"
    }, session_maker)
    assert "export_url" in res
    assert res["export_url"] == "/api/v1/clients/export"
