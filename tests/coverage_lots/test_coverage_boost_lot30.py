"""
test_coverage_boost_lot30.py
Targets:
  - manager.py: connect_database auto-create database (lines 293-310), db_transaction savepoint exception paths (lines 592-596, 608-609)
  - tool_actions_operations.py: delete_operation for sale_finished (lines 88-100)
  - tool_actions_contacts.py: modify_client with fields (lines 30-60)
  - sales/commands.py: create_sale_record with raw item kind & sale type determination (lines 92-101)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — connect_database auto-create DB & savepoint errors
# ============================================================

def test_manager_connect_database_creates_db_when_missing():
    """Lines 293-310: connect_database auto-creates database if missing."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    mock_engine1 = MagicMock()
    mock_engine1.raw_connection.side_effect = Exception("database \"missing_db\" does not exist (3D000)")

    mock_conn2 = MagicMock()
    mock_engine2 = MagicMock()
    mock_engine2.raw_connection.return_value = mock_conn2

    mock_admin_conn = MagicMock()

    with patch.object(mgr, "get_database_engine", side_effect=[mock_engine1, mock_engine2]), \
         patch("app.core.db_helpers.manager.create_engine") as mock_create_engine:
        mock_admin_engine = MagicMock()
        mock_admin_engine.connect.return_value.__enter__.return_value = mock_admin_conn
        mock_create_engine.return_value = mock_admin_engine

        conn = mgr.connect_database("postgresql://user:pass@localhost:5432/missing_db")

    assert conn is not None
    mock_admin_conn.execute.assert_called()


def test_manager_db_transaction_savepoint_rollback_error():
    """Lines 592-596: savepoint rollback error is caught and logged."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()
    mock_db = MagicMock()
    # 1st execute is SAVEPOINT (succeeds), 2nd execute is ROLLBACK TO SAVEPOINT (fails)
    mock_db.execute.side_effect = [MagicMock(), Exception("savepoint rollback fail")]

    from app.core.request_state import push_request_state, reset_request_state
    from fastapi import Request

    req = Request({"type": "http", "method": "GET", "path": "/t", "query_string": b"", "headers": []})
    token = push_request_state(
        request=req, db=mock_db, session={}, request_id="t_sp",
        audit_source="api", user=None, g=SimpleNamespace(user=None), csp_nonce="n"
    )
    try:
        from app.core.request_state import get_request_state
        state = get_request_state()
        state.db_tx_depth = 1  # Nested transaction depth > 0

        with patch.object(mgr, "get_write_db", return_value=mock_db):
            with pytest.raises(ValueError):
                with mgr.db_transaction():
                    raise ValueError("trigger rollback")
    finally:
        reset_request_state(token)


def test_manager_db_transaction_savepoint_release_error():
    """Lines 608-609: savepoint release error is caught and logged."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()
    mock_db = MagicMock()
    # SAVEPOINT succeeds, RELEASE SAVEPOINT fails
    mock_db.execute.side_effect = [MagicMock(), Exception("release fail")]

    from app.core.request_state import push_request_state, reset_request_state
    from fastapi import Request

    req = Request({"type": "http", "method": "GET", "path": "/t2", "query_string": b"", "headers": []})
    token = push_request_state(
        request=req, db=mock_db, session={}, request_id="t_sp2",
        audit_source="api", user=None, g=SimpleNamespace(user=None), csp_nonce="n2"
    )
    try:
        from app.core.request_state import get_request_state
        state = get_request_state()
        state.db_tx_depth = 1

        with patch.object(mgr, "get_write_db", return_value=mock_db):
            with mgr.db_transaction():
                pass  # Succeeded, triggers release savepoint
    finally:
        reset_request_state(token)


# ============================================================
# 2. tool_actions_operations.py — delete_operation finished sale
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_delete_operation_sale_finished():
    """Lines 88-100: delete_operation with tx_kind='sale_finished'."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.sales.service import SalesService

    with patch.object(SalesService, "delete_sale_by_id", new=AsyncMock(return_value=True)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "delete_operation",
            {"tx_kind": "sale_finished", "tx_id": 42},
            mock_session_maker,
        )
    assert result.get("success") is True


# ============================================================
# 3. tool_actions_contacts.py — modify_client with fields
# ============================================================

@pytest.mark.asyncio
async def test_handle_contacts_modify_client():
    """Lines 30-60: modify_client with name, phone, address, notes."""
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.clients.service import ClientService

    mock_client = MagicMock()
    mock_client.name = "Client Original"

    with patch.object(ClientService, "get_client", new=AsyncMock(return_value=mock_client)), \
         patch.object(ClientService, "update_client", new=AsyncMock(return_value=mock_client)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_contacts(
            "modify_client",
            {
                "client_id": 1,
                "name": "Nouveau Nom",
                "phone": "0550123456",
                "address": "Zone Industrielle",
                "notes": "VIP Client"
            },
            mock_session_maker,
        )
    assert result.get("success") is True
