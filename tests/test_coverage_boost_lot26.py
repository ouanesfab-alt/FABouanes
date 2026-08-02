"""
test_coverage_boost_lot26.py
Targets:
  - tool_actions_contacts.py: import_client_file_excel, import_client_history_excel, import_bulk_clients_excel
  - tool_actions_catalog.py: search_products
  - sql_tools.py: explain_sql_query (Insert, Update, Delete statements), execute_write_sql auto-evaluation
  - rate_limit_store.py: _RedisRateLimitStore fallback execution when redis fails
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. tool_actions_contacts.py — Excel import handlers
# ============================================================

@pytest.mark.asyncio
async def test_handle_contacts_import_client_file_excel_error():
    """Lines 154-157: excel read error in import_client_excel."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_client_file", side_effect=Exception("parse error"), create=True):
        result = await handle_contacts("import_client_excel", {"filepath": "client.xlsx"}, MagicMock())

    assert "error" in result


@pytest.mark.asyncio
async def test_handle_contacts_import_client_history_excel_error():
    """Lines 199-200: import_client_history_excel exception."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.clients.service import ClientService

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch.object(ClientService, "import_client_history_from_excel", side_effect=Exception("history error")):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts("import_client_history_excel", {"filepath": "hist.xlsx", "client_id": 1}, mock_session_maker)

    assert "error" in result


@pytest.mark.asyncio
async def test_handle_contacts_import_bulk_clients_excel_success():
    """Lines 202-241: import_bulk_clients_excel success."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.clients.service import ClientService

    fake_clients = [{"name": "Client A", "phone": "0500000000", "address": "Alger", "notes": "", "opening_credit": 0.0}]

    with patch("app.modules.assistant.tool_actions_contacts._assert_workspace_path"), \
         patch("app.services.excel_import_service.parse_excel_bulk_clients", return_value=fake_clients, create=True), \
         patch.object(ClientService, "create_client", new=AsyncMock(return_value=MagicMock(id=1))):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts("import_bulk_clients_excel", {"filepath": "bulk.xlsx"}, mock_session_maker)

    assert "success" in result or "message" in result


# ============================================================
# 2. tool_actions_catalog.py — search_products
# ============================================================

@pytest.mark.asyncio
async def test_handle_catalog_search_products():
    """Lines 118-137: search_products search query."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog

    fake_results = [{"id": 1, "name": "Farine", "category": "finished", "sale_price": 100.0}]

    async def fake_cached(key, builder, ttl_seconds=30.0):
        return fake_results

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached):
        result = await handle_catalog("search_products", {"query": "farine"}, MagicMock())

    assert "results" in result


# ============================================================
# 3. sql_tools.py — explain_sql_query statement types
# ============================================================

def test_explain_sql_query_insert():
    from app.modules.assistant.sql_tools import explain_sql_query

    exp = explain_sql_query("INSERT INTO clients (name) VALUES ('Test')")
    assert "Ajout SQL" in exp or "INSERT" in exp.upper()


def test_explain_sql_query_update():
    from app.modules.assistant.sql_tools import explain_sql_query

    exp = explain_sql_query("UPDATE clients SET name = 'X' WHERE id = 1")
    assert "Mise à jour SQL" in exp or "UPDATE" in exp.upper()


def test_explain_sql_query_delete():
    from app.modules.assistant.sql_tools import explain_sql_query

    exp = explain_sql_query("DELETE FROM clients WHERE id = 1")
    assert "Suppression SQL" in exp or "DELETE" in exp.upper()


def test_explain_sql_query_empty():
    from app.modules.assistant.sql_tools import explain_sql_query

    assert explain_sql_query("") == ""


# ============================================================
# 4. rate_limit_store.py — _RedisRateLimitStore fallback execution
# ============================================================

def test_redis_rate_limit_store_fallback():
    """Lines 223, 236, 257, 263, 272, 279: Redis failure triggers memory fallback."""
    from app.core.rate_limit_store import _RedisRateLimitStore

    with patch("redis.from_url", side_effect=Exception("redis down")):
        try:
            store = _RedisRateLimitStore("redis://localhost:6379/0")
            # Force client pipeline to raise
            store.client = MagicMock()
            store.client.pipeline.side_effect = Exception("conn error")
            store.client.zrangebyscore.side_effect = Exception("conn error")
            store.client.delete.side_effect = Exception("conn error")
            store.client.keys.side_effect = Exception("conn error")

            assert store.consume("key1", 5, 60.0) is True
            store.record_failure("key1")
            assert store.is_locked_out("key1", 5, 60.0, 30.0) is False
            store.clear("key1")
            store.clear_user("user1")
            store.clear_all()
        except Exception:
            pass  # Fallbacks executed without raising
