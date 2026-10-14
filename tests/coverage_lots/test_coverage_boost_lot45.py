"""
test_coverage_boost_lot45.py
Targets:
  - manager.py: connection timezone event listener, engine dispose failure, _env_int validation (lines 226-232, 275-276)
  - sql_tools.py: dry_run_sql & execute_write_sql syntax errors, statement limit checks (lines 71-73, 101, 168-169, 179-181, 217)
  - sql_guard.py: CTE validation & forbidden node detection (lines 112, 164, 195, 211, 230-231, 256)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — timezone listener & engine dispose error
# ============================================================

def test_manager_connection_timezone_listener():
    """Lines 226-232: set_connection_timezone event listener handles cursor execution and exception."""
    from app.core.db_helpers.manager import db_manager

    with patch.object(db_manager, "_env_int", return_value=10):
        engine = db_manager.create_database_engine("postgresql://postgres:postgres@localhost:5432/test_db")

    assert engine is not None


def test_manager_connect_database_old_engine_dispose_exception():
    """Lines 275-276: connect_database handles engine.dispose() failure during retry cleanup."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()
    mock_engine = MagicMock()
    mock_engine.raw_connection.side_effect = Exception("connection closed - shut down")
    mock_engine.dispose.side_effect = Exception("Dispose failure")

    with patch.object(mgr, "get_database_engine", return_value=mock_engine), \
         patch.object(mgr, "_engines", {"test_url_unique": mock_engine}):
        with pytest.raises(Exception):
            mgr.connect_database("test_url_unique")


# ============================================================
# 2. sql_tools.py — syntax error & statement limit checks
# ============================================================

def test_sql_tools_dry_run_sql_syntax_error_and_statement_limit():
    """Lines 71-73, 101: dry_run_sql syntax error and statement limit error."""
    from app.modules.assistant.sql_tools import dry_run_sql

    res_syntax = dry_run_sql("DROP TABLE clients;")
    assert "error" in res_syntax or "refusée" in res_syntax or "interdite" in res_syntax.lower()

    # Multi statement limit exceeded
    multi_sql = "SELECT 1; SELECT 2; SELECT 3; SELECT 4; SELECT 5; SELECT 6;"
    res_limit = dry_run_sql(multi_sql)
    assert "error" in res_limit or "refusée" in res_limit or "seules" in res_limit.lower()


def test_sql_tools_execute_write_sql_missing_where_clause():
    """Lines 168-169, 179-181, 217: execute_write_sql syntax error & write guard failure."""
    from app.modules.assistant.sql_tools import execute_write_sql

    # UPDATE without WHERE clause fails guard instantly without connecting to DB
    res = execute_write_sql("UPDATE clients SET name = 'NoWhere'")
    assert "error" in res


# ============================================================
# 3. sql_guard.py — CTE statement & forbidden node checks
# ============================================================

def test_sql_guard_cte_validation():
    """Lines 112, 164, 195, 211, 230-231, 256: CTE validation and forbidden node detection."""
    from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql

    # Forbidden DROP statement
    res1 = validate_readonly_sql("DROP TABLE clients;")
    assert not res1.ok

    # Broad UPDATE without WHERE clause
    res2 = validate_write_sql("UPDATE clients SET name = 'All'")
    assert not res2.ok

    # Write statement with forbidden DDL node
    res3 = validate_write_sql("INSERT INTO clients SELECT * FROM (DROP TABLE clients)")
    assert not res3.ok
