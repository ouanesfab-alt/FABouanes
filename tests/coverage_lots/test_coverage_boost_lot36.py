"""
test_coverage_boost_lot36.py
Targets:
  - sql_tools.py:
    - dry_run_sql balance change formatting & dry-run error handling (lines 48, 71-73, 107, 111)
    - execute_readonly_sql statement timeout & generic SQL error (lines 132, 133)
    - execute_write_sql empty parse & no WHERE clause warning & dict preview fallback (lines 148, 168-169, 179-181)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch



# ============================================================
# 1. sql_tools.py — dry_run_sql edge cases
# ============================================================

def test_dry_run_sql_balance_change():
    """Lines 71-73, 107: dry_run_sql formats client balance changes."""
    from app.modules.assistant.sql_tools import dry_run_sql

    mock_conn = MagicMock()
    # 1st execute: SET LOCAL timeout, 2nd: before balances, 3rd: query, 4th: after balances
    mock_cur1 = MagicMock(fetchall=MagicMock(return_value=[(1, "Client A", 100.0)]))
    mock_cur2 = MagicMock(fetchone=MagicMock(return_value={"id": 42}), rowcount=1)
    mock_cur3 = MagicMock(fetchall=MagicMock(return_value=[(1, "Client A", 200.0)]))

    mock_conn.execute.side_effect = [MagicMock(), mock_cur1, mock_cur2, mock_cur3]

    with patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = dry_run_sql("UPDATE clients SET current_balance = 200.0 WHERE id = 1")

    assert "Client A" in res
    assert "100.00 DA" in res
    assert "200.00 DA" in res


def test_dry_run_sql_empty_statements():
    """Line 48: dry_run_sql returns error when sqlglot parse yields empty statements."""
    from app.modules.assistant.sql_tools import dry_run_sql

    with patch("sqlglot.parse", return_value=[]):
        res = dry_run_sql("UPDATE clients SET name = 'X' WHERE id = 1")
    assert "invalide" in res.lower() or "refusée" in res.lower()


def test_dry_run_sql_execution_failed():
    """Line 111: dry_run_sql catches unexpected execution failures."""
    from app.modules.assistant.sql_tools import dry_run_sql

    with patch("app.modules.assistant.sql_tools.db_manager.db_transaction", side_effect=Exception("connection drop")):
        res = dry_run_sql("INSERT INTO clients (name) VALUES ('Y')")
    assert "échoué" in res.lower() or "error" in res.lower()


# ============================================================
# 2. sql_tools.py — execute_readonly_sql & execute_write_sql
# ============================================================

def test_execute_readonly_sql_timeout():
    """Line 132: execute_readonly_sql handles statement timeout error."""
    from app.modules.assistant.sql_tools import execute_readonly_sql

    with patch("app.modules.assistant.sql_tools.db_manager.db_transaction", side_effect=Exception("canceling statement due to statement timeout")):
        res = execute_readonly_sql("SELECT * FROM sales")

    assert "error" in res
    assert "10s" in res["error"] or "trop de temps" in res["error"].lower()


def test_execute_readonly_sql_generic_error():
    """Line 133: execute_readonly_sql returns formatted SQL error."""
    from app.modules.assistant.sql_tools import execute_readonly_sql

    with patch("app.modules.assistant.sql_tools.db_manager.db_transaction", side_effect=Exception("relation 'nonexistent' does not exist")):
        res = execute_readonly_sql("SELECT * FROM nonexistent")

    assert "error" in res
    assert "nonexistent" in res["error"]


def test_execute_write_sql_where_clause_auto_evaluation():
    """Lines 179-181: execute_write_sql auto-evaluates affected rows with WHERE clause."""
    from app.modules.assistant.sql_tools import execute_write_sql

    mock_rows = [{"id": 1}, {"id": 2}]
    mock_conn = MagicMock()
    mock_cur = MagicMock(rowcount=2)
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.query_db", return_value=mock_rows), \
         patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("DELETE FROM clients WHERE id > 0")

    assert res.get("success") is True
    assert "auto_evaluation" in res
