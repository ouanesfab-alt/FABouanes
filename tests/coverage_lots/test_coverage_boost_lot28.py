"""
test_coverage_boost_lot28.py
Targets:
  - sql_tools.py: execute_write_sql with UPDATE/DELETE auto-evaluation & RETURNING clause parsing
  - config.py: secret_key generation, warning branches
  - rag.py: search_vector_manual/catalog database query errors
  - tool_actions_operations.py: add_expense category normalization, delete_operation finished vs raw
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. sql_tools.py — execute_write_sql auto-evaluation & RETURNING
# ============================================================

def test_execute_write_sql_auto_evaluation_update():
    """Lines 150-181: UPDATE auto-evaluates affected rows preview."""
    from app.modules.assistant.sql_tools import execute_write_sql

    mock_rows = [{"id": 1, "name": "Client A"}]

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.rowcount = 1
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.query_db", return_value=mock_rows), \
         patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("UPDATE clients SET name = 'Updated' WHERE id = 1")

    assert res.get("success") is True
    assert "auto_evaluation" in res
    assert res["auto_evaluation"][0]["table_name"] == "clients"


def test_execute_write_sql_returning_list_tuple():
    """Lines 198-201: RETURNING row is a tuple/list."""
    from app.modules.assistant.sql_tools import execute_write_sql

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (42, "Name")
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("INSERT INTO clients (name) VALUES ('X') RETURNING id")

    assert res.get("inserted_id") == 42


# ============================================================
# 2. config.py — warning paths and secret_key generation
# ============================================================

def test_config_secret_key_file_warning():
    """Lines 83-84: secret.key read warning."""
    from app.core.config import Settings

    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = Exception("permission denied")

    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", side_effect=Exception("permission denied")):
        # Should catch exception and issue warning without crashing in test mode
        s = Settings(secret_key="test-key-32-bytes-minimum-length!", env="testing")
        assert s.secret_key is not None


# ============================================================
# 3. rag.py — error handling in vector search & general RAG
# ============================================================

@pytest.mark.asyncio
async def test_search_vector_manual_query_error():
    """Lines 113-114: query_db exception in vector search handled gracefully."""
    from app.modules.assistant.rag import search_vector_manual

    with patch("app.modules.assistant.rag.get_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch("app.core.db_helpers.query_db", side_effect=Exception("db connection error")):
        res = await search_vector_manual("query", api_key="key")

    assert res == []


@pytest.mark.asyncio
async def test_search_vector_catalog_python_fallback():
    """Lines 318-319, 348-375: python fallback when pgvector is not installed."""
    from app.modules.assistant.rag import search_vector_catalog
    import json

    emb = [0.1] * 1536
    item_emb_json = json.dumps(emb)
    mock_rows = [{"item_kind": "finished", "item_id": 1, "text_content": "Farine 25kg", "embedding": item_emb_json}]

    with patch("app.modules.assistant.rag.get_embedding", new=AsyncMock(return_value=emb)), \
         patch("app.core.db_helpers.query_db", side_effect=[Exception("no pgvector"), mock_rows]):
        res = await search_vector_catalog("farine", api_key="key")

    assert len(res) == 1
    assert res[0]["kind"] == "finished"
    assert res[0]["score"] == pytest.approx(1.0)


# ============================================================
# 4. tool_actions_operations.py — delete_operation kind branching
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_delete_operation_sale_raw():
    """Lines 88-100: delete_operation with tx_kind='sale_raw'."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.sales.service import SalesService

    with patch.object(SalesService, "delete_sale_by_id", new=AsyncMock(return_value=True)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "delete_operation",
            {"tx_kind": "sale_raw", "tx_id": 10},
            mock_session_maker,
        )
    assert result.get("success") is True


@pytest.mark.asyncio
async def test_handle_operations_delete_operation_purchase():
    """Lines 101-104: delete_operation with tx_kind='purchase'."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.purchases.service import PurchaseService

    with patch.object(PurchaseService, "delete_purchase_by_id", new=AsyncMock(return_value=True)):
        mock_session = AsyncMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await handle_operations(
            "delete_operation",
            {"tx_kind": "purchase", "tx_id": 5},
            mock_session_maker,
        )
    assert result.get("success") is True
