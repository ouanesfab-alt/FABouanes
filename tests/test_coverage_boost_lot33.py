"""
test_coverage_boost_lot33.py
Targets:
  - tool_actions_contacts.py: import_client_excel success, import_bulk_clients_excel exception handling
  - tool_actions_catalog.py: modify_product raw material & not found, import_bulk_products_excel exception path
  - tool_actions_insights.py: search_web status code error & exception handling
  - sql_guard.py: validate_readonly_sql & validate_write_sql edge error cases
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. tool_actions_contacts.py — import_client_excel success & bulk errors
# ============================================================

@pytest.mark.asyncio
async def test_handle_contacts_import_client_excel_success():
    """Lines 158-171: import_client_excel happy path."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.clients.service import ClientService

    fake_data = {"name": "Client Import", "phone": "0600000000", "address": "Alger", "notes": "", "opening_credit": 1000.0, "history_count": 5}

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_client_file", return_value=fake_data, create=True), \
         patch.object(ClientService, "create_client", new=AsyncMock(return_value=MagicMock(id=42))):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        res = await handle_contacts("import_client_excel", {"filepath": "client.xlsx"}, mock_session_maker)

    assert res.get("success") is True
    assert res.get("client_id") == 42


@pytest.mark.asyncio
async def test_handle_contacts_import_bulk_clients_excel_single_fail():
    """Lines 234-235: individual client failure during bulk import."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.clients.service import ClientService

    fake_clients = [{"name": "Client 1", "phone": "05", "address": "", "notes": "", "opening_credit": 0},
                    {"name": "Client 2", "phone": "06", "address": "", "notes": "", "opening_credit": 0}]

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_clients", return_value=fake_clients, create=True), \
         patch.object(ClientService, "create_client", side_effect=[MagicMock(id=1), Exception("duplicate")]):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        res = await handle_contacts("import_bulk_clients_excel", {"filepath": "bulk.xlsx"}, mock_session_maker)

    assert res.get("success") is True
    assert "1/2" in res.get("message", "")


# ============================================================
# 2. tool_actions_catalog.py — modify_product raw & bulk exception
# ============================================================

@pytest.mark.asyncio
async def test_handle_catalog_modify_product_raw_not_found():
    """Lines 84-87: modify_product raw material not found."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.catalog.service import CatalogService

    with patch.object(CatalogService, "get_raw_material", new=AsyncMock(return_value=None)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        res = await handle_catalog("modify_product", {"product_id": 99, "category": "raw", "name": "New Name"}, mock_session_maker)

    assert "error" in res


@pytest.mark.asyncio
async def test_handle_catalog_import_bulk_products_excel_single_fail():
    """Lines 183-184: individual product failure during bulk product import."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.catalog.service import CatalogService

    fake_products = [{"name": "P1", "unit": "kg", "stock_qty": 10, "avg_cost": 5, "sale_price": 8, "alert_threshold": 2}]

    with patch("app.modules.assistant.tool_actions_catalog._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_products", return_value=fake_products, create=True), \
         patch.object(CatalogService, "create_raw_material", side_effect=Exception("create raw fail")):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        res = await handle_catalog("import_bulk_products_excel", {"filepath": "p.xlsx", "is_raw_material": True}, mock_session_maker)

    assert res.get("success") is True
    assert "0/1" in res.get("message", "")


# ============================================================
# 3. tool_actions_insights.py — search_web HTTP errors
# ============================================================

@pytest.mark.asyncio
async def test_search_web_duckduckgo_http_status_error():
    """Lines 24-25: DuckDuckGo returns non-200 HTTP status."""
    from app.modules.assistant.tool_actions_insights import search_web

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    async def fake_cached(key, builder, ttl_seconds=300.0):
        return await builder()

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached), \
         patch("httpx.AsyncClient", return_value=mock_client):
        res = await search_web("farine algérie")

    assert "error" in res
    assert "403" in res["error"]
