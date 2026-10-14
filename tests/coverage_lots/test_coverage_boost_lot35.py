"""
test_coverage_boost_lot35.py
Targets:
  - manager.py:
    - CompatCursor.close exception handling (lines 63-64)
    - CompatConnection.execute non-str query conversion (line 113)
    - CompatConnection.execute 25P02 transaction aborted retry & rollback exception (lines 124-125, 128-130)
    - CompatConnection._reset_postgres_connection close exception & reconnect (lines 138, 167-168)
    - CompatConnection.executescript (lines 140-145)
  - tool_actions_insights.py:
    - get_current_weather non-200 status code & HTTP exception (lines 45-46, 48, 65-66, 121-123)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — CompatCursor and CompatConnection edge cases
# ============================================================

def test_compat_cursor_close_exception():
    """Lines 63-64: CompatCursor.close handles exception gracefully."""
    from app.core.db_helpers.manager import CompatCursor

    mock_cur = MagicMock()
    mock_cur.close.side_effect = Exception("close error")

    cursor = CompatCursor(mock_cur)
    # Should not crash
    cursor.close()


def test_compat_connection_non_str_query_and_executescript():
    """Lines 113, 140-145: CompatConnection accepts non-str query and executescript."""
    from app.core.db_helpers.manager import CompatConnection

    mock_raw_conn = MagicMock()
    mock_cur = MagicMock()
    mock_raw_conn.cursor.return_value = mock_cur

    conn = CompatConnection(mock_raw_conn)
    # Non-str query object
    class NonStrQuery:
        def __str__(self):
            return "SELECT 1"

    cur = conn.execute(NonStrQuery())
    assert cur is not None

    conn.executescript("SELECT 1; SELECT 2;")
    assert mock_raw_conn.cursor.call_count >= 2


def test_compat_connection_transaction_aborted_retry():
    """Lines 124-125, 128-130: 25P02 transaction aborted triggers retry."""
    from app.core.db_helpers.manager import CompatConnection

    mock_raw_conn = MagicMock()
    mock_raw_conn.rollback.side_effect = Exception("rollback err")

    mock_cur1 = MagicMock()
    mock_cur1.execute.side_effect = Exception("ERROR: 25P02: current transaction is aborted")

    mock_cur2 = MagicMock()

    mock_raw_conn.cursor.side_effect = [mock_cur1, mock_cur2]

    conn = CompatConnection(mock_raw_conn)
    cur = conn.execute("SELECT 1")
    assert cur is not None


def test_compat_connection_reset_postgres_connection():
    """Lines 138, 167-168: _reset_postgres_connection handles close error and reconnects."""
    from app.core.db_helpers.manager import CompatConnection

    mock_old = MagicMock()
    mock_old.close.side_effect = Exception("close err")

    mock_new = MagicMock()

    reconnect_fn = MagicMock(return_value=mock_new)

    conn = CompatConnection(mock_old, reconnect=reconnect_fn)
    conn._reset_postgres_connection()

    assert conn.conn is mock_new
    reconnect_fn.assert_called_once()


# ============================================================
# 2. tool_actions_insights.py — weather API HTTP errors
# ============================================================

@pytest.mark.asyncio
async def test_handle_insights_get_current_weather_http_error():
    """Lines 45-46, 48, 121-123: get_current_weather handles HTTP 404 or connection failure."""
    from app.modules.assistant.tool_actions_insights import handle_insights

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    async def fake_cached(key, builder, ttl_seconds=600.0):
        return await builder()

    with patch("app.core.perf_cache.async_cached_result", side_effect=fake_cached), \
         patch("httpx.AsyncClient", return_value=mock_client):
        res = await handle_insights("get_current_weather", {"location": "NonExistentCity"}, MagicMock())

    assert "error" in res
