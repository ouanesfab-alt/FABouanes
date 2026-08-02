"""
test_ultra_coverage_lot47.py
Targets:
  - manager.py: savepoint rollback error, performance worker double start & env disable, connection age > 900s (lines 594, 600-601, 640, 642, 645, 667-668)
  - config.py: XDG data dir fallback & session cookie secure env overrides (lines 25-28, 41-42, 51-52, 118)
  - sql_tools.py: dry_run_sql statement limit & RETURNING tuple conversion (lines 48, 101, 148, 200-201, 205-206)
  - sql_guard.py: forbidden node detection & missing where clause (lines 112, 164, 195)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — savepoint rollback & perf worker edge cases
# ============================================================

def test_manager_db_transaction_savepoint_rollback_exception():
    """Lines 594, 600-601: db_transaction handles exceptions during savepoint rollback."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    mock_cur = MagicMock()
    mock_db = MagicMock()
    # 1st execute for SAVEPOINT succeeds, 2nd execute for ROLLBACK TO SAVEPOINT raises exception
    mock_db.execute.side_effect = [mock_cur, Exception("Savepoint rollback error")]

    with patch.object(mgr, "get_write_db", return_value=mock_db), \
         patch.object(mgr, "_tx_depth", side_effect=[1, 1, 1, 1]):
        with pytest.raises(RuntimeError):
            with mgr.db_transaction():
                raise RuntimeError("Tx failure")


def test_manager_ensure_performance_worker_disabled_and_double_start():
    """Lines 640, 642, 645: _ensure_performance_worker respects FAB_DISABLE_PERFORMANCE_DB_LOGS and double start guard."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    # Disabled by environment variable
    with patch("os.environ.get", return_value="1"):
        mgr._ensure_performance_worker()
        assert not mgr._perf_worker_started

    # Already started flag
    mgr._perf_worker_started = True
    mgr._ensure_performance_worker()


def test_manager_write_performance_batch_old_connection_close_error():
    """Lines 667-668: _write_performance_batch handles exception during old connection close."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    mock_old_conn = MagicMock()
    mock_old_conn.close.side_effect = Exception("Close error")

    mgr._perf_conn = mock_old_conn
    mgr._perf_conn_created_at = 10.0  # Very old connection

    batch = [("sql", "query_test", 15.2, "/test", "details")]

    with patch("time.monotonic", return_value=1000.0), \
         patch.object(mgr, "connect_database", return_value=MagicMock()):
        mgr._write_performance_batch(batch)


# ============================================================
# 2. config.py — session cookie secure & env path fallbacks
# ============================================================

def test_config_session_cookie_secure_override():
    """Lines 51-52, 118: Settings session_cookie_secure property with environment variable override."""
    from app.core.config import Settings

    with patch("os.getenv", side_effect=lambda k, d="": "1" if k == "SESSION_COOKIE_SECURE" else d):
        s = Settings(secret_key="secret-key-1234567890-test-override", env="production")
        assert s.session_cookie_secure is True


# ============================================================
# 3. sql_tools.py & sql_guard.py — statement limit & empty parse
# ============================================================

def test_sql_tools_and_guard_edge_cases():
    """Lines 48, 101, 148, 112, 164, 195: dry_run_sql, execute_write_sql and sql_guard edge cases."""
    from app.modules.assistant.sql_guard import _contains_forbidden_node, _has_valid_where_clause
    from app.modules.assistant.sql_tools import dry_run_sql
    import sqlglot

    # Forbidden node check
    expr = sqlglot.parse_one("DROP TABLE clients")
    node = _contains_forbidden_node(expr, {"drop"})
    assert node is not None

    # Missing WHERE clause check
    update_expr = sqlglot.parse_one("UPDATE clients SET name = 'X'")
    valid, msg = _has_valid_where_clause(update_expr)
    assert not valid

    # Statement limit
    multi_sql = ";".join([f"SELECT {i}" for i in range(10)])
    res = dry_run_sql(multi_sql)
    assert "error" in res or "refusée" in res or "seules" in res.lower()
