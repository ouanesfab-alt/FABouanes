"""Tests de couverture ciblés — Lot 6.

Couvre: assistant/tool_actions_contacts.py (handle_contacts)
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch


# ── tool_actions_contacts.py (71% → target ~95%) ───────────────────


@pytest.mark.asyncio
async def test_handle_contacts_unknown_func():
    """handle_contacts returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    res = await handle_contacts("unknown_action", {}, MagicMock())
    assert res is None


@pytest.mark.asyncio
async def test_handle_contacts_add_client():
    """handle_contacts add_client creates client via service."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    client_mock = MagicMock()
    client_mock.id = 10

    with patch("app.modules.clients.service.ClientService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.create_client.return_value = client_mock
        mock_srv_cls.return_value = mock_srv

        args = {"name": "Test Client", "phone": "0550123456", "address": "Alger", "opening_credit": "500.0"}
        res = await handle_contacts("add_client", args, session_maker)

        assert res == {"success": True, "client_id": 10}


@pytest.mark.asyncio
async def test_handle_contacts_modify_client_success():
    """handle_contacts modify_client updates existing client."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.clients.service.ClientService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.update_client.return_value = True
        mock_srv_cls.return_value = mock_srv

        args = {"client_id": 10, "name": "Updated Name", "phone": "0550999888"}
        res = await handle_contacts("modify_client", args, session_maker)

        assert res == {"success": True, "message": "Client 10 modifié."}


@pytest.mark.asyncio
async def test_handle_contacts_modify_client_not_found():
    """handle_contacts modify_client returns error if client not found."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.clients.service.ClientService") as mock_srv_cls:
        mock_srv = AsyncMock()
        existing_client = MagicMock()
        existing_client.name = "Existing Client"
        mock_srv.get_client.return_value = existing_client
        mock_srv.update_client.return_value = False
        mock_srv_cls.return_value = mock_srv

        args = {"client_id": 99}
        res = await handle_contacts("modify_client", args, session_maker)

        assert "error" in res


@pytest.mark.asyncio
async def test_handle_contacts_delete_client_success():
    """handle_contacts delete_client deletes existing client."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.clients.service.ClientService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.delete_client.return_value = True
        mock_srv_cls.return_value = mock_srv

        res = await handle_contacts("delete_client", {"client_id": 5}, session_maker)

        assert res == {"success": True, "message": "Client 5 supprimé."}


@pytest.mark.asyncio
async def test_handle_contacts_delete_client_failure():
    """handle_contacts delete_client returns error if deletion fails."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.clients.service.ClientService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.delete_client.return_value = False
        mock_srv_cls.return_value = mock_srv

        res = await handle_contacts("delete_client", {"client_id": 5}, session_maker)

        assert "error" in res


@pytest.mark.asyncio
async def test_handle_contacts_add_supplier():
    """handle_contacts add_supplier creates supplier via service."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.services.contact_directory_service.create_supplier_from_form", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = 12
        args = {"name": "Fournisseur A", "phone": "021000000", "address": "Oran"}
        res = await handle_contacts("add_supplier", args, session_maker)

        assert res == {"success": True, "supplier_id": 12}


@pytest.mark.asyncio
async def test_handle_contacts_modify_supplier_success():
    """handle_contacts modify_supplier updates existing supplier."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    existing_supplier = {"id": 2, "name": "Old Supplier", "phone": "021111111", "address": "Oran", "notes": ""}

    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock) as mock_get, \
         patch("app.services.contact_directory_service.update_supplier_from_form", new_callable=AsyncMock):

        mock_get.return_value = existing_supplier
        args = {"supplier_id": 2, "name": "New Supplier Name"}
        res = await handle_contacts("modify_supplier", args, session_maker)

        assert res == {"success": True, "message": "Fournisseur 2 modifie."}


@pytest.mark.asyncio
async def test_handle_contacts_modify_supplier_not_found():
    """handle_contacts modify_supplier returns error if supplier not found."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        res = await handle_contacts("modify_supplier", {"supplier_id": 99}, session_maker)

        assert "error" in res


@pytest.mark.asyncio
async def test_handle_contacts_delete_supplier_success():
    """handle_contacts delete_supplier deletes supplier with no linked purchases."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    mock_res_purchases = MagicMock()
    mock_res_purchases.scalar.return_value = 0
    mock_res_docs = MagicMock()
    mock_res_docs.scalar.return_value = 0
    mock_session.execute.side_effect = [mock_res_purchases, mock_res_docs]

    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock) as mock_get, \
         patch("app.services.contact_directory_service.delete_supplier_by_id", new_callable=AsyncMock):

        mock_get.return_value = {"id": 3}
        res = await handle_contacts("delete_supplier", {"supplier_id": 3}, session_maker)

        assert res == {"success": True, "message": "Fournisseur 3 supprime."}


@pytest.mark.asyncio
async def test_handle_contacts_delete_supplier_linked_purchases():
    """handle_contacts delete_supplier refuses deletion if supplier has linked purchases."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    mock_res_purchases = MagicMock()
    mock_res_purchases.scalar.return_value = 5  # 5 purchases linked
    mock_session.execute.return_value = mock_res_purchases

    with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": 3}
        res = await handle_contacts("delete_supplier", {"supplier_id": 3}, session_maker)

        assert "error" in res
        assert "refusee" in res["error"] or "achats" in res["error"]


@pytest.mark.asyncio
async def test_handle_contacts_search_clients():
    """handle_contacts search_clients executes SQL query and returns results."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    mock_row = (1, "Client A", "0550112233", Decimal("1500.00"))
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    async def mock_cache_impl(key, builder, ttl_seconds=30.0):
        return await builder()

    with patch("app.core.perf_cache.async_cached_result", side_effect=mock_cache_impl):
        res = await handle_contacts("search_clients", {"query": "Client A"}, session_maker)

        assert "results" in res
        assert len(res["results"]) == 1
        assert res["results"][0]["name"] == "Client A"
        assert res["results"][0]["debt"] == 1500.0

