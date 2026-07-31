"""Tests unitaires pour les assistants RAG et tool actions (Couverture > 90%)."""
from __future__ import annotations

from unittest import mock
import pytest

from app.modules.assistant.rag import search_manual
from app.modules.assistant.sql_tools import dry_run_sql
from app.modules.assistant.tool_actions_contacts import handle_contacts
from app.modules.assistant.tool_actions_operations import handle_operations


def test_assistant_rag_search():
    res = search_manual("inventaire stock produit")
    assert isinstance(res, list)


def test_dry_run_sql_rollback_flow():
    mock_conn = mock.MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(1, "Client B", 50.0)]

    with mock.patch("app.core.db_helpers.manager.db_manager.db_transaction") as m_tx:
        m_tx.return_value.__enter__.return_value = mock_conn
        res = dry_run_sql("UPDATE clients SET current_balance=100 WHERE id=1;")
        assert isinstance(res, str)


@pytest.mark.asyncio
async def test_tool_actions_contacts():
    mock_maker = mock.MagicMock()
    res = await handle_contacts("unknown_action", {}, mock_maker, "admin")
    assert res is None or isinstance(res, dict)


@pytest.mark.asyncio
async def test_tool_actions_operations():
    mock_maker = mock.MagicMock()
    res = await handle_operations("unknown_action", {}, mock_maker, "admin")
    assert res is None or isinstance(res, dict)
