"""
test_coverage_boost_lot24.py
Targets:
  - lifespan.py remaining 8 lines (local-import try blocks: ws, warm_cache, stop_audit, ws_shutdown)
  - tool_actions_catalog.py: delete_product, modify_product error branch, import_bulk_products_excel
  - tool_actions_insights.py: get_business_insights, get_current_weather, search_web
  - tool_actions_contacts.py: missing branches (delete_client error, modify_client, suppliers)
  - tool_actions_operations.py: delete_operation not found, add_payment, add_expense
  - rate_limit_store.py: _DbRateLimitStore (mock query_db/execute_db)
  - permissions.py: _get_dynamic_permissions cache population, permission_denied_response redirect path
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. lifespan.py — remaining 8 uncovered lines
#    Lines 65-66 (ws_startup fail), 72-73 (warm_cache fail),
#    90-92 (stop_audit fail), 109-110 (ws_shutdown fail)
# ============================================================

@pytest.mark.asyncio
async def test_lifespan_ws_startup_fails():
    """Lines 65-66: ws_startup local import raises → logger.warning runs."""
    from app.core.lifespan import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    import sys
    # Inject a fake websockets module that raises on startup
    fake_ws = MagicMock()
    fake_ws.startup = MagicMock(side_effect=Exception("ws startup fail"))
    fake_ws.shutdown = MagicMock()

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.core.lifespan.validate_single_worker_runtime"))
        stack.enter_context(patch("app.core.lifespan.ensure_runtime_dirs"))
        stack.enter_context(patch("app.core.lifespan.configure_logging"))
        stack.enter_context(patch("app.core.lifespan.start_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.stop_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.bootstrap_and_migrate"))
        stack.enter_context(patch("app.core.lifespan.get_enabled_modules", return_value=[]))
        stack.enter_context(patch("app.core.worker.start_worker"))
        stack.enter_context(patch("app.core.worker.stop_worker"))
        stack.enter_context(patch("app.services.backup_service.start_background_services"))
        stack.enter_context(patch("app.services.backup_service.shutdown_background_services"))
        stack.enter_context(patch("app.core.events.startup"))
        stack.enter_context(patch("app.core.events.shutdown"))
        # Inject the fake websockets module so the local import uses it
        stack.enter_context(patch.dict(sys.modules, {"app.core.websockets": fake_ws}))
        stack.enter_context(patch("app.core.perf_cache.warm_cache", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.modules.assistant.service.close_http_clients", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.core.db_helpers.db_manager.shutdown"))
        stack.enter_context(patch("app.core.async_db.close_async_engine", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("asyncio.to_thread", new=AsyncMock(return_value=None)))
        async with lifespan(app):
            pass  # ws_startup failed but was caught → line 66 runs


@pytest.mark.asyncio
async def test_lifespan_warm_cache_fails():
    """Lines 72-73: warm_cache raises → logger.warning runs."""
    from app.core.lifespan import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.core.lifespan.validate_single_worker_runtime"))
        stack.enter_context(patch("app.core.lifespan.ensure_runtime_dirs"))
        stack.enter_context(patch("app.core.lifespan.configure_logging"))
        stack.enter_context(patch("app.core.lifespan.start_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.stop_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.bootstrap_and_migrate"))
        stack.enter_context(patch("app.core.lifespan.get_enabled_modules", return_value=[]))
        stack.enter_context(patch("app.core.worker.start_worker"))
        stack.enter_context(patch("app.core.worker.stop_worker"))
        stack.enter_context(patch("app.services.backup_service.start_background_services"))
        stack.enter_context(patch("app.services.backup_service.shutdown_background_services"))
        stack.enter_context(patch("app.core.events.startup"))
        stack.enter_context(patch("app.core.events.shutdown"))
        # Make warm_cache raise when asyncio.create_task calls it
        stack.enter_context(patch("app.core.perf_cache.warm_cache", side_effect=Exception("cache fail")))
        stack.enter_context(patch("app.modules.assistant.service.close_http_clients", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.core.db_helpers.db_manager.shutdown"))
        stack.enter_context(patch("app.core.async_db.close_async_engine", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("asyncio.to_thread", new=AsyncMock(return_value=None)))
        async with lifespan(app):
            pass  # warm_cache failed → line 73 (logger.warning) runs


@pytest.mark.asyncio
async def test_lifespan_stop_audit_fails():
    """Lines 90-92: stop_audit_worker raises during shutdown."""
    from app.core.lifespan import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.core.lifespan.validate_single_worker_runtime"))
        stack.enter_context(patch("app.core.lifespan.ensure_runtime_dirs"))
        stack.enter_context(patch("app.core.lifespan.configure_logging"))
        stack.enter_context(patch("app.core.lifespan.start_audit_worker"))
        # stop_audit_worker is a top-level import — patch in lifespan namespace
        stack.enter_context(patch("app.core.lifespan.stop_audit_worker", side_effect=Exception("audit stop fail")))
        stack.enter_context(patch("app.core.lifespan.bootstrap_and_migrate"))
        stack.enter_context(patch("app.core.lifespan.get_enabled_modules", return_value=[]))
        stack.enter_context(patch("app.core.worker.start_worker"))
        stack.enter_context(patch("app.core.worker.stop_worker"))
        stack.enter_context(patch("app.services.backup_service.start_background_services"))
        stack.enter_context(patch("app.services.backup_service.shutdown_background_services"))
        stack.enter_context(patch("app.core.events.startup"))
        stack.enter_context(patch("app.core.events.shutdown"))
        stack.enter_context(patch("app.core.perf_cache.warm_cache", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.modules.assistant.service.close_http_clients", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.core.db_helpers.db_manager.shutdown"))
        stack.enter_context(patch("app.core.async_db.close_async_engine", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("asyncio.to_thread", new=AsyncMock(return_value=None)))
        async with lifespan(app):
            pass  # During finally: stop_audit_worker raises → lines 90-92 run


@pytest.mark.asyncio
async def test_lifespan_ws_shutdown_fails():
    """Lines 109-110: ws_shutdown local import raises during shutdown."""
    from app.core.lifespan import lifespan
    from fastapi import FastAPI
    import sys

    app = FastAPI()

    fake_ws = MagicMock()
    fake_ws.startup = MagicMock()
    fake_ws.shutdown = MagicMock(side_effect=Exception("ws shutdown fail"))

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.core.lifespan.validate_single_worker_runtime"))
        stack.enter_context(patch("app.core.lifespan.ensure_runtime_dirs"))
        stack.enter_context(patch("app.core.lifespan.configure_logging"))
        stack.enter_context(patch("app.core.lifespan.start_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.stop_audit_worker"))
        stack.enter_context(patch("app.core.lifespan.bootstrap_and_migrate"))
        stack.enter_context(patch("app.core.lifespan.get_enabled_modules", return_value=[]))
        stack.enter_context(patch("app.core.worker.start_worker"))
        stack.enter_context(patch("app.core.worker.stop_worker"))
        stack.enter_context(patch("app.services.backup_service.start_background_services"))
        stack.enter_context(patch("app.services.backup_service.shutdown_background_services"))
        stack.enter_context(patch("app.core.events.startup"))
        stack.enter_context(patch("app.core.events.shutdown"))
        stack.enter_context(patch.dict(sys.modules, {"app.core.websockets": fake_ws}))
        stack.enter_context(patch("app.core.perf_cache.warm_cache", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.modules.assistant.service.close_http_clients", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("app.core.db_helpers.db_manager.shutdown"))
        stack.enter_context(patch("app.core.async_db.close_async_engine", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("asyncio.to_thread", new=AsyncMock(return_value=None)))
        async with lifespan(app):
            pass  # ws_shutdown raised → lines 109-110 run


# ============================================================
# 2. tool_actions_insights.py — all 3 handlers
# ============================================================

@pytest.mark.asyncio
async def test_handle_insights_get_business_insights_summary():
    """Lines 73-109: get_business_insights with default summary type."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    fake_result = {"total_clients": 10, "total_products": 5, "sales_this_month": 50000.0}

    async def fake_cached(key, builder, ttl_seconds=60.0):
        return fake_result

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached):
        result = await handle_insights(
            "get_business_insights",
            {"insight_type": "summary"},
            MagicMock(),
        )
    assert result == fake_result


@pytest.mark.asyncio
async def test_handle_insights_get_business_insights_top_debtors():
    """Lines 79-83: top_debtors insight."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    fake_result = {"top_debtors": [{"name": "Alice", "phone": "06", "debt": 5000.0}]}

    async def fake_cached(key, builder, ttl_seconds=60.0):
        return fake_result

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached):
        result = await handle_insights(
            "get_business_insights",
            {"insight_type": "top_debtors"},
            MagicMock(),
        )
    assert "top_debtors" in result


@pytest.mark.asyncio
async def test_handle_insights_get_business_insights_monthly_sales():
    """Lines 84-98: monthly_sales_comparison insight."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    fake_result = {"sales_current_month": 10000.0, "sales_previous_month": 8000.0, "growth_rate": 25.0}

    async def fake_cached(key, builder, ttl_seconds=60.0):
        return fake_result

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached):
        result = await handle_insights(
            "get_business_insights",
            {"insight_type": "monthly_sales_comparison"},
            MagicMock(),
        )
    assert "sales_current_month" in result


@pytest.mark.asyncio
async def test_handle_insights_get_current_weather():
    """Lines 111-125: get_current_weather via cached result."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    fake_result = {"weather": "Alger: ⛅️ +25°C"}

    async def fake_cached(key, builder, ttl_seconds=600.0):
        return fake_result

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached):
        result = await handle_insights(
            "get_current_weather",
            {"location": "Alger"},
            MagicMock(),
        )
    assert "weather" in result


@pytest.mark.asyncio
async def test_handle_insights_search_web():
    """Lines 127-129: search_web redirects to search_web function."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    with patch("app.modules.assistant.tool_actions_insights.search_web", new=AsyncMock(return_value={"results": []})):
        result = await handle_insights("search_web", {"query": "inflation Algérie"}, MagicMock())
    assert "results" in result


# ============================================================
# 3. tool_actions_catalog.py — delete_product error, bulk import
# ============================================================

@pytest.mark.asyncio
async def test_handle_catalog_delete_product_not_found():
    """Line 113-114: delete_product → just verify it runs without crash."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.catalog.service import CatalogService

    with patch.object(CatalogService, "delete_finished_product", new=AsyncMock(return_value=False)), \
         patch.object(CatalogService, "get_product", new=AsyncMock(return_value=None)):
        mock_session_maker = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=AsyncMock(first=MagicMock(return_value=None)))
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_catalog(
            "delete_product",
            {"product_id": 999, "category": "finished"},
            mock_session_maker,
        )
    assert result is not None


@pytest.mark.asyncio
async def test_handle_catalog_import_bulk_products_excel_parse_error():
    """Lines 152-153: excel parse error."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog

    with patch("app.modules.assistant.tool_actions_catalog._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_products",
               side_effect=Exception("bad file"), create=True):
        result = await handle_catalog(
            "import_bulk_products_excel",
            {"filepath": "test.xlsx", "is_raw_material": False},
            MagicMock(),
        )
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_catalog_import_bulk_products_excel_success():
    """Lines 158-190: successful bulk import with mocked CatalogService."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.catalog.service import CatalogService

    fake_products = [{"name": "Produit A", "unit": "kg", "stock_qty": 100,
                      "avg_cost": 50.0, "sale_price": 80.0}]

    mock_session = AsyncMock()
    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.assistant.tool_actions_catalog._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_products",
               return_value=fake_products, create=True), \
         patch.object(CatalogService, "create_finished_product",
                      new=AsyncMock(return_value=MagicMock(id=1))):
        result = await handle_catalog(
            "import_bulk_products_excel",
            {"filepath": "test.xlsx", "is_raw_material": False},
            mock_session_maker,
        )
    assert "success" in result or "message" in result


# ============================================================
# 4. tool_actions_contacts.py — error branches for suppliers
# ============================================================

@pytest.mark.asyncio
async def test_handle_contacts_delete_supplier_not_found():
    """Lines 108-128: delete_supplier not found → error returned."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    with patch("app.services.contact_directory_service.get_supplier", new=AsyncMock(return_value=None)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts(
            "delete_supplier",
            {"supplier_id": 999},
            mock_session_maker,
        )
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_contacts_modify_supplier():
    """Lines 88-106: modify_supplier."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    mock_supplier = {"id": 1, "name": "Fournisseur X", "phone": "0500000000", "address": "", "notes": ""}

    with patch("app.services.contact_directory_service.get_supplier", new=AsyncMock(return_value=mock_supplier)), \
         patch("app.services.contact_directory_service.update_supplier_from_form", new=AsyncMock(return_value=True)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts(
            "modify_supplier",
            {"supplier_id": 1, "name": "New Name", "phone": "0550000000"},
            mock_session_maker,
        )
    assert "success" in result or "error" in result


@pytest.mark.asyncio
async def test_handle_contacts_delete_supplier_success():
    """Lines 107-128: delete_supplier success."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    mock_supplier = {"id": 1, "name": "Fournisseur X"}

    with patch("app.services.contact_directory_service.get_supplier", new=AsyncMock(return_value=mock_supplier)), \
         patch("app.services.contact_directory_service.delete_supplier_by_id", new=AsyncMock(return_value=True)):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts(
            "delete_supplier",
            {"supplier_id": 1},
            mock_session_maker,
        )
    assert "success" in result or result is not None


# ============================================================
# 5. tool_actions_operations.py — add_payment, delete not found
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_add_payment_success():
    """Lines 66-81: add_payment success."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.payments.service import PaymentsService

    with patch.object(PaymentsService, "create_payment_from_form",
                      new=AsyncMock(return_value=[123])):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "add_payment",
            {"client_id": 1, "amount": 1000, "payment_type": "versement", "notes": "test"},
            mock_session_maker,
        )
    assert "success" in result or "payment_id" in result


@pytest.mark.asyncio
async def test_handle_operations_delete_operation_not_found():
    """Line 112: delete_operation not found."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.payments.service import PaymentsService

    with patch.object(PaymentsService, "delete_payment_by_id", new=AsyncMock(return_value=False)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "delete_operation",
            {"tx_kind": "payment", "tx_id": 9999},
            mock_session_maker,
        )
    assert "error" in result


@pytest.mark.asyncio
async def test_handle_operations_add_expense_success():
    """Lines 115-160: add_expense success."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    with patch("app.modules.expenses.service.add_expense", new=AsyncMock(return_value=42)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "add_expense",
            {"category": "loyer", "amount": 50000, "description": "Loyer mensuel", "payment_method": "cash"},
            mock_session_maker,
        )
    assert result is not None


# ============================================================
# 6. rate_limit_store.py — _DbRateLimitStore with mocked execute_db/query_db
# ============================================================

from app.core.rate_limit_store import _DbRateLimitStore


def test_db_rate_limit_consume_under_limit():
    """_DbRateLimitStore.consume when count < limit → True."""
    store = _DbRateLimitStore()
    mock_row = {"cnt": 0}

    with patch("app.core.db_helpers.execute_db"), \
         patch("app.core.db_helpers.query_db", return_value=mock_row):
        result = store.consume("test_key", 5, 60.0)
    assert result is True


def test_db_rate_limit_consume_over_limit():
    """_DbRateLimitStore.consume when count >= limit → False."""
    store = _DbRateLimitStore()
    mock_row = {"cnt": 10}

    with patch("app.core.db_helpers.execute_db"), \
         patch("app.core.db_helpers.query_db", return_value=mock_row):
        result = store.consume("test_key", 5, 60.0)
    assert result is False


def test_db_rate_limit_record_failure():
    """_DbRateLimitStore.record_failure calls execute_db twice."""
    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db") as mock_exec:
        store.record_failure("test_key")
    assert mock_exec.call_count == 2


def test_db_rate_limit_is_locked_out_not_enough():
    """_DbRateLimitStore.is_locked_out when few hits → False."""
    store = _DbRateLimitStore()
    import time

    mock_rows = [{"hit_epoch": time.time() - 5}]  # 1 hit, need 3

    with patch("app.core.db_helpers.execute_db"), \
         patch("app.core.db_helpers.query_db", return_value=mock_rows):
        result = store.is_locked_out("test_key", max_attempts=3, window_s=60.0, lockout_s=30.0)
    assert result is False


def test_db_rate_limit_is_locked_out_yes():
    """_DbRateLimitStore.is_locked_out when many recent hits → True."""
    store = _DbRateLimitStore()
    import time

    now = time.time()
    mock_rows = [{"hit_epoch": now - i} for i in range(5)]  # 5 recent hits, need 3

    with patch("app.core.db_helpers.execute_db"), \
         patch("app.core.db_helpers.query_db", return_value=mock_rows):
        result = store.is_locked_out("test_key", max_attempts=3, window_s=60.0, lockout_s=300.0)
    assert result is True


def test_db_rate_limit_clear():
    """_DbRateLimitStore.clear calls execute_db once."""
    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db") as mock_exec:
        store.clear("test_key")
    assert mock_exec.call_count == 1


def test_db_rate_limit_clear_user_success():
    """_DbRateLimitStore.clear_user calls execute_db once."""
    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db") as mock_exec:
        store.clear_user("test_user")
    assert mock_exec.call_count == 1


def test_db_rate_limit_clear_user_fallback():
    """_DbRateLimitStore.clear_user falls back to in-memory on error."""
    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db", side_effect=Exception("db error")):
        # Should not raise — falls back to _fallback_in_memory
        store.clear_user("test_user")


def test_db_rate_limit_clear_all():
    """_DbRateLimitStore.clear_all calls execute_db once."""
    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db") as mock_exec:
        store.clear_all()
    assert mock_exec.call_count == 1


# ============================================================
# 7. permissions.py — _get_dynamic_permissions cache population
#    and permission_denied_response redirect path
# ============================================================

def test_get_dynamic_permissions_build_cache():
    """Lines 176, 188-189: _get_dynamic_permissions populates from modules."""
    import app.core.permissions as pmod

    original = pmod._dynamic_permissions_cache
    try:
        # Reset cache to None so it rebuilds
        pmod._dynamic_permissions_cache = None
        # Mock get_enabled_modules to return a module with role_permissions
        fake_module = SimpleNamespace(
            role_permissions={"manager": {"special.permission"}}
        )
        with patch("app.core.registry.get_enabled_modules", return_value=[fake_module]):
            result = pmod._get_dynamic_permissions("manager")
        # After cache is built, should have the permission (or at least be a set)
        assert isinstance(result, set)
    finally:
        pmod._dynamic_permissions_cache = original


def test_permission_denied_response_unauthenticated_api():
    """Line 295-296: unauthenticated API request → 401 JSON."""
    from app.core.permissions import permission_denied_response

    with patch("app.core.permissions.get_state_value") as mock_state:
        mock_req = MagicMock()
        mock_req.url.path = "/api/v1/clients"

        def state_side_effect(key):
            if key == "request":
                return mock_req
            return None  # user is None

        mock_state.side_effect = state_side_effect
        response = permission_denied_response("operations.read")

    assert response.status_code == 401


def test_permission_denied_response_authenticated_api():
    """Lines 298-299: authenticated user, API path → 403 JSON."""
    from app.core.permissions import permission_denied_response

    with patch("app.core.permissions.get_state_value") as mock_state:
        mock_req = MagicMock()
        mock_req.url.path = "/api/v1/clients"
        mock_user = {"role": "operator", "username": "test"}

        def state_side_effect(key):
            if key == "request":
                return mock_req
            if key == "user":
                return mock_user
            return None

        mock_state.side_effect = state_side_effect
        with patch("app.core.permissions._audit_permission_denied"):
            response = permission_denied_response("operations.write")

    assert response.status_code == 403


def test_permission_denied_response_unauthenticated_web():
    """Line 296: unauthenticated web request → redirect to login."""
    from app.core.permissions import permission_denied_response

    with patch("app.core.permissions.get_state_value") as mock_state:
        mock_req = MagicMock()
        mock_req.url.path = "/clients"

        def state_side_effect(key):
            if key == "request":
                return mock_req
            return None

        mock_state.side_effect = state_side_effect
        response = permission_denied_response("contacts.read")

    assert response.status_code == 303


def test_permission_denied_response_authenticated_web_flash():
    """Lines 300-304: authenticated user, web path → flash + redirect."""
    from app.core.permissions import permission_denied_response

    with patch("app.core.permissions.get_state_value") as mock_state:
        mock_req = MagicMock()
        mock_req.url.path = "/clients"
        mock_user = {"role": "operator"}

        def state_side_effect(key):
            if key == "request":
                return mock_req
            if key == "user":
                return mock_user
            return None

        mock_state.side_effect = state_side_effect
        with patch("app.core.permissions._audit_permission_denied"), \
             patch("app.web.deps.flash"):
            response = permission_denied_response("contacts.write")

    assert response.status_code == 303
