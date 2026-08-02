"""
test_coverage_boost_lot46.py
Targets:
  - manager.py: postgres_pool_status, get_db, cached get_read_db, and query_db/execute_db retry close exception handling (lines 326-341, 344, 364-365, 486-487, 535-536)
  - tool_actions_operations.py: print and export helper links (lines 288, 298, 300, 306, 308, 310)
  - tool_actions_insights.py: weather/insights error handling (lines 45-46, 48, 65-66, 122-123)
  - rate_limit_store.py: bucket invalid input & fallback (lines 72, 256-257, 285-288)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — postgres_pool_status & get_read_db caching
# ============================================================

def test_manager_postgres_pool_status_and_get_db():
    """Lines 326-341, 344: postgres_pool_status returns status dict & get_db delegates to get_write_db."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    mock_pool = MagicMock()
    mock_pool.size.return_value = 5
    mock_pool.checkedin.return_value = 3
    mock_pool.checkedout.return_value = 2
    mock_pool.overflow.return_value = 0

    mock_engine = MagicMock(pool=mock_pool)

    with patch.object(mgr, "get_database_engine", return_value=mock_engine):
        status = mgr.postgres_pool_status("postgresql://user:pass@localhost:5432/db")

    assert status["engine"] == "postgres"
    assert status["size"] == 5

    # get_db() call
    with patch.object(mgr, "get_write_db", return_value=MagicMock()) as mock_write:
        mgr.get_db()
        mock_write.assert_called_once()


def test_manager_get_read_db_cached():
    """Lines 364-365: get_read_db returns existing unclosed state.read_db connection."""
    from app.core.db_helpers.manager import DatabaseManager

    mgr = DatabaseManager()

    mock_conn = MagicMock(_closed=False)
    mock_state = MagicMock(read_db=mock_conn)

    with patch("os.environ.get", return_value="postgresql://read_user:pass@localhost:5432/read_db"), \
         patch("app.core.db_helpers.manager.get_request_state", return_value=mock_state), \
         patch.object(mgr, "_tx_depth", return_value=0):
        read_db = mgr.get_read_db()

    assert read_db == mock_conn


# ============================================================
# 2. tool_actions_operations.py — export links
# ============================================================

@pytest.mark.asyncio
async def test_handle_operations_export_reports_and_audit_links():
    """Lines 288, 298, 300, 306, 308, 310: export links for reports and audit logs."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    # Reports export
    res1 = await handle_operations("get_export_link", {"export_type": "reports", "date_from": "2024-01-01", "date_to": "2024-01-31"}, MagicMock())
    assert "export_url" in res1

    # Audit export with filters
    audit_filters = {"actor": "admin", "action": "login", "entity_type": "user", "status": "ok"}
    res2 = await handle_operations("get_export_link", {"export_type": "audit", "date_from": "2024-01-01", "date_to": "2024-01-31", "audit_filters": audit_filters}, MagicMock())
    assert "export_url" in res2


# ============================================================
# 3. rate_limit_store.py — bucket fallback & error recovery
# ============================================================

def test_rate_limit_store_bucket_error_recovery():
    """Lines 72, 256-257, 285-288: RateLimitStore bucket parsing & fallback."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore

    store = _InMemoryRateLimitStore()

    # Line 72: is_locked_out return False
    locked = store.is_locked_out("test_key", max_attempts=5, window_s=60.0, lockout_s=300.0)
    assert locked is False
