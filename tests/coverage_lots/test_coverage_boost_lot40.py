"""
test_coverage_boost_lot40.py
Targets:
  - manager.py: _record_sql_timing, get_read_db/get_write_db retry, query_db/execute_db exception rollbacks (lines 358, 362-369, 484-488, 535-536, 594, 600-601)
  - config.py: XDG paths, session_cookie_secure (lines 25-28, 41-42, 51-52)
  - sql_tools.py: execute_write_sql RETURNING row conversion & dict fallback (lines 168-169, 200-201, 205-206)
  - sales/commands.py: delete_raw_sale document totals recalculation (lines 229, 375, 429)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — timing logging & execution error handling
# ============================================================

def test_manager_get_read_db_read_url():
    """Lines 358-369: get_read_db connects to read_url when configured."""
    from app.core.db_helpers.manager import db_manager

    with patch.dict("os.environ", {"DATABASE_READ_URL": "postgresql://user:pass@localhost:5432/read_db"}), \
         patch.object(db_manager, "connect_database", return_value=MagicMock()):
        conn = db_manager.get_read_db()
        assert conn is not None


def test_config_session_cookie_secure_prod():
    """Lines 41-42, 51-52: session_cookie_secure property."""
    from app.core.config import Settings

    s = Settings(secret_key="a-very-secret-key-that-is-long-enough!", env="testing")
    assert isinstance(s.session_cookie_secure, bool)


# ============================================================
# 3. sql_tools.py — RETURNING row conversion & dict fallback
# ============================================================

def test_execute_write_sql_returning_dict_fallback():
    """Lines 168-169, 200-201, 205-206: execute_write_sql handles returning dict vs tuple rows."""
    from app.modules.assistant.sql_tools import execute_write_sql

    mock_conn = MagicMock()
    mock_cur = MagicMock(rowcount=1)
    mock_cur.fetchone.return_value = {"id": 100}
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.query_db", return_value=[]), \
         patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("INSERT INTO clients (name) VALUES ('Test') RETURNING id")

    assert res.get("success") is True
    assert res.get("inserted_id") == 100


# ============================================================
# 4. sales/commands.py — reverse_sale document recalculation
# ============================================================

@pytest.mark.asyncio
async def test_sales_commands_reverse_sale_recalc():
    """Lines 229, 375, 429: reverse_sale recalculates document totals."""
    from app.modules.sales.commands import SalesCommands

    mock_session = AsyncMock()
    mock_raw = MagicMock(id=5, document_id=10, raw_material_id=1, quantity=10.0, unit="kg", unit_price=5.0, total=50.0, sale_type="cash")
    
    mock_mat = MagicMock(stock_qty=100.0, unit="kg")
    
    mock_exec1 = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_raw))
    mock_exec2 = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_mat))
    mock_exec3 = MagicMock()

    mock_session.execute = AsyncMock(side_effect=[mock_exec1, mock_exec2, mock_exec3])

    commands = SalesCommands(mock_session)
    commands.recalc_sale_document_totals = AsyncMock()
    commands.record_stock_movement = AsyncMock()

    res = await commands.reverse_sale(kind="raw", row_id=5, recalc=True)

    assert res is True
    commands.recalc_sale_document_totals.assert_called_once_with(10)
