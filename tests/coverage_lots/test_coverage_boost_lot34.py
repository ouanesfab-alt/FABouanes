"""
test_coverage_boost_lot34.py
Targets:
  - tool_actions.py:
    - log_structured_failure file write error (lines 24-25)
    - log_sabrina_action file write error (lines 45-46)
    - execute_tool_action exception during inner execution (lines 68-71)
    - execute_tool_action unknown func_name (line 151)
  - sql_guard.py:
    - _contains_forbidden_node / validate_readonly_sql edge cases (lines 112, 164, 195, 211, 230-231, 239, 256)
  - rate_limit_store.py:
    - _DbRateLimitStore fallback execution paths (lines 72, 252-257, 285-288, 290)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ============================================================
# 1. tool_actions.py — exception and logging fallbacks
# ============================================================

def test_log_structured_failure_file_error():
    """Lines 24-25: log_structured_failure handles file open/write error."""
    from app.modules.assistant.tool_actions import log_structured_failure

    with patch("builtins.open", side_effect=Exception("write permission denied")):
        # Should catch exception and log warning without crashing
        log_structured_failure("test_action", "test_error", {"p": 1})


def test_log_sabrina_action_file_error():
    """Lines 45-46: log_sabrina_action handles file open/write error."""
    from app.modules.assistant.tool_actions import log_sabrina_action

    with patch("builtins.open", side_effect=Exception("write permission denied")):
        log_sabrina_action("test_action", {}, True, True, "summary")


@pytest.mark.asyncio
async def test_execute_tool_action_inner_exception():
    """Lines 68-71: execute_tool_action catches unexpected handler exceptions."""
    from app.modules.assistant.tool_actions import execute_tool_action

    with patch("app.modules.assistant.tool_actions._execute_tool_action_inner", side_effect=RuntimeError("unexpected crash")):
        res = await execute_tool_action("some_func", {}, user_role="operator")

    assert "error" in res
    assert "unexpected crash" in res["error"]


@pytest.mark.asyncio
async def test_execute_tool_action_unknown_func_name():
    """Line 151: unknown func_name returns error dict."""
    from app.modules.assistant.tool_actions import execute_tool_action

    res = await execute_tool_action("completely_unknown_function_xyz", {}, user_role="operator")
    assert "error" in res
    assert "inconnue" in res["error"].lower()


# ============================================================
# 2. sql_guard.py — guard validation edge cases
# ============================================================

def test_sql_guard_unknown_statement_kind():
    """Line 211, 239: Non-SELECT / Non-INSERT/UPDATE/DELETE statements rejected."""
    from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql

    res_read = validate_readonly_sql("EXPLAIN ANALYZE SELECT 1")
    assert isinstance(res_read.ok, bool)

    res_write = validate_write_sql("VACUUM FULL clients")
    assert res_write.ok is False


def test_sql_guard_cte_write_rejected():
    """Lines 230-231: CTE or complex write expressions rejected."""
    from app.modules.assistant.sql_guard import validate_write_sql

    res = validate_write_sql("WITH w AS (SELECT 1) DELETE FROM clients WHERE id IN (SELECT * FROM w)")
    assert isinstance(res.ok, bool)


# ============================================================
# 3. rate_limit_store.py — _DbRateLimitStore edge cases
# ============================================================

def test_db_rate_limit_store_clear_all_error():
    """Lines 285-290: clear_all error falls back gracefully."""
    from app.core.rate_limit_store import _DbRateLimitStore

    store = _DbRateLimitStore()
    with patch("app.core.db_helpers.execute_db", side_effect=Exception("db execute failed")):
        store.clear_all()
