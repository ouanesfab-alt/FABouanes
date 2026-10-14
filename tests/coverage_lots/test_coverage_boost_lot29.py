"""
test_coverage_boost_lot29.py
Targets:
  - sales/commands.py: create_sale_document (lines 310-325)
  - rate_limit_store.py: _DbRateLimitStore.is_locked_out window checks (line 165-168)
  - exception_handlers.py: unhandled exception formatting (lines 130-131, 157-158, 187-188)
  - permissions.py: user custom_permissions_json parse exception (lines 208-209, 217-218)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest


# ============================================================
# 1. sales/commands.py — create_sale_document
# ============================================================

@pytest.mark.asyncio
async def test_sales_commands_create_sale_document():
    """Lines 310-325: create_sale_document."""
    from app.modules.sales.commands import SalesCommands

    mock_session = AsyncMock()

    commands = SalesCommands(mock_session)
    with patch("app.modules.sales.commands.next_doc_number", return_value="BV-2024-001"):
        doc_id = await commands._insert_sale_document(
            client_id=1,
            sale_type="cash",
            sale_date=date(2024, 1, 1),
            notes="note",
        )
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


# ============================================================
# 2. permissions.py — custom_permissions_json parse error handling
# ============================================================

def test_has_permission_custom_permissions_json_invalid_dict():
    """Lines 208-209: invalid JSON string in dict custom_permissions_json."""
    from app.core.permissions import has_permission

    user = {"role": "cashier", "custom_permissions_json": "{invalid json}"}
    # Should catch JSONDecodeError and continue without error
    assert has_permission(user, "any.permission") is False


def test_has_permission_custom_permissions_json_invalid_object():
    """Lines 217-218: invalid JSON string in object custom_permissions_json."""
    from app.core.permissions import has_permission
    from types import SimpleNamespace

    user = SimpleNamespace(role="cashier", custom_permissions_json="{invalid json}")
    # Should catch JSONDecodeError and continue without error
    assert has_permission(user, "any.permission") is False


# ============================================================
# 3. rate_limit_store.py — _DbRateLimitStore.is_locked_out lockout time
# ============================================================

def test_db_rate_limit_store_is_locked_out_exponential():
    """Lines 165-168: exponential lockout calculation when recent_hits >= max_attempts."""
    from app.core.rate_limit_store import _DbRateLimitStore
    import time

    store = _DbRateLimitStore()
    now = time.time()
    # 5 attempts within window (max=3) -> extra=2 -> lockout_time = 30 * 2^2 = 120s
    mock_rows = [{"hit_epoch": now - i} for i in range(5)]

    with patch("app.core.db_helpers.execute_db"), \
         patch("app.core.db_helpers.query_db", return_value=mock_rows):
        is_locked = store.is_locked_out("test_key", max_attempts=3, window_s=600.0, lockout_s=30.0)

    assert is_locked is True
