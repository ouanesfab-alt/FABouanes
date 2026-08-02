"""
test_coverage_boost_lot41.py
Targets:
  - users.py model: custom_permissions_list JSON error (lines 36-37), _coerce_bool int input (lines 43-45)
  - tool_actions_admin.py: modify_app_file workspace error (line 36), user not found (lines 83, 94), user creation fail (line 69)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. users.py — model property and validator coverage
# ============================================================

def test_users_model_custom_permissions_invalid_json():
    """Lines 36-37: custom_permissions_list returns [] when custom_permissions_json is corrupt."""
    from app.core.models_pkg.users import User

    u = User(username="testuser", password_hash="hash", custom_permissions_json="INVALID JSON {")
    assert u.custom_permissions_list == []


def test_users_model_coerce_bool():
    """Lines 43-45: _coerce_bool coerces integers 0/1 to boolean values."""
    from app.core.models_pkg.users import User

    b1 = User._coerce_bool(1)
    assert b1 is True

    b0 = User._coerce_bool(0)
    assert b0 is False

    b_true = User._coerce_bool(True)
    assert b_true is True


# ============================================================
# 2. tool_actions_admin.py — admin tool error branches
# ============================================================

@pytest.mark.asyncio
async def test_handle_admin_modify_app_file_outside_workspace():
    """Lines 35-36: modify_app_file returns security error when path is outside workspace."""
    from app.modules.assistant.tool_actions_admin import handle_admin

    res = await handle_admin("modify_app_file", {"filepath": "/etc/passwd"}, MagicMock(), user_role="admin")
    assert "error" in res


@pytest.mark.asyncio
async def test_handle_admin_create_app_user_failure():
    """Line 69: create_app_user handles rejected creation response."""
    from app.modules.assistant.tool_actions_admin import handle_admin

    with patch("app.services.admin_service.create_user_account", new=AsyncMock(return_value={"ok": False, "message": "Creation refuser"})):
        res = await handle_admin("create_app_user", {"username": "baduser", "password": "pwd"}, MagicMock(), user_role="admin")

    assert "error" in res


@pytest.mark.asyncio
async def test_handle_admin_change_password_user_not_found():
    """Line 83: change_app_user_password user not found."""
    from app.modules.assistant.tool_actions_admin import handle_admin

    with patch("app.services.auth_service.get_user_by_username", new=AsyncMock(return_value=None)):
        res = await handle_admin("change_app_user_password", {"username": "nobody", "new_password": "StrongPassword123!"}, MagicMock(), user_role="admin")

    assert "error" in res


@pytest.mark.asyncio
async def test_handle_admin_delete_user_not_found():
    """Line 94: delete_app_user user not found."""
    from app.modules.assistant.tool_actions_admin import handle_admin

    with patch("app.services.auth_service.get_user_by_username", new=AsyncMock(return_value=None)):
        res = await handle_admin("delete_app_user", {"username": "nobody"}, MagicMock(), user_role="admin")

    assert "error" in res
