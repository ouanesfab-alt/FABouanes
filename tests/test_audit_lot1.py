from __future__ import annotations

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.core.jwt_auth import create_refresh_token


@pytest.mark.asyncio
async def test_refresh_token_db_failure_raises_500():
    """Verify that if api_refresh_tokens DB insertion fails, no token is returned and 500 is raised (Lot 1.2)."""
    with patch("app.core.db_helpers.execute_db", side_effect=Exception("DB write failure")):
        with pytest.raises(HTTPException) as exc_info:
            create_refresh_token(user_id=9999)
        assert exc_info.value.status_code == 500
        assert "Impossible de sécuriser la session mobile" in exc_info.value.detail


@pytest.mark.asyncio
async def test_account_lockout_logic():
    """Unit test for account lockout functions (Lot 1.1)."""
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.users.repository import (
        _record_account_login_failure_impl,
        _unlock_user_account_impl,
    )

    # 1. Mock DB session returning failed_login_count = 4 (so 5th attempt locks out)
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = 5
    mock_session.execute.return_value = mock_res

    cnt, locked = await _record_account_login_failure_impl(
        user_id=10, max_attempts=5, lockout_minutes=15, db=mock_session
    )
    assert cnt == 5
    assert locked is True
    assert mock_session.execute.call_count == 2

    # 2. Test unlock user account impl
    mock_session_unlock = AsyncMock()
    mock_res_uname = MagicMock()
    mock_res_uname.scalar_one_or_none.return_value = "admin_user"
    mock_res_up = MagicMock()
    mock_res_up.rowcount = 1
    mock_session_unlock.execute.side_effect = [mock_res_uname, mock_res_up]

    unlocked = await _unlock_user_account_impl(user_id=10, db=mock_session_unlock)
    assert unlocked is True


def test_no_raw_print_in_app_directory():
    """AST lint test to ensure no raw print(...) function calls exist in the app/ codebase (Lot 1.3)."""
    import ast
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent / "app"
    forbidden_prints = []

    for py_file in app_dir.rglob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(code, filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                forbidden_prints.append(f"{py_file.name}:{node.lineno}")

    assert not forbidden_prints, f"Raw print() calls found in app/ directory: {forbidden_prints}"


def test_get_audit_stats_returns_dict():
    """Verify get_audit_stats returns queue metrics dict."""
    from app.core.audit import get_audit_stats
    stats = get_audit_stats()
    assert isinstance(stats, dict)
    assert "audit_queue_size" in stats
    assert "audit_dropped" in stats
    assert isinstance(stats["audit_queue_size"], int)
    assert isinstance(stats["audit_dropped"], int)
    assert stats["audit_queue_size"] >= 0
    assert stats["audit_dropped"] >= 0


def test_security_headers_no_xss_protection():
    """Verify X-XSS-Protection is no longer set (obsolete header removed)."""
    from unittest.mock import MagicMock, patch
    from app.core.security import security_headers

    mock_response = MagicMock()
    mock_response.headers = {}
    with patch("app.core.security.get_state_value", return_value=None):
        result = security_headers(mock_response)
    assert "X-XSS-Protection" not in result.headers


def test_security_headers_no_version_in_production():
    """Verify X-App-Version is hidden in production server mode."""
    from unittest.mock import MagicMock, patch
    from app.core.security import security_headers

    mock_response = MagicMock()
    mock_response.headers = {}
    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.security.get_state_value", return_value=None):
        mock_settings.desktop_mode = False
        mock_settings.env = "production"
        mock_settings.strict_csp = False
        result = security_headers(mock_response)
    assert "X-App-Version" not in result.headers


def test_security_headers_version_exposed_in_desktop():
    """Verify X-App-Version IS present in desktop mode."""
    from unittest.mock import MagicMock, patch
    from app.core.security import security_headers

    mock_response = MagicMock()
    mock_response.headers = {}
    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.security.get_state_value", return_value=None):
        mock_settings.desktop_mode = True
        mock_settings.env = "production"
        mock_settings.strict_csp = False
        result = security_headers(mock_response)
    assert "X-App-Version" in result.headers
    assert result.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"


def test_security_headers_hsts_in_production():
    """Verify HSTS is set in non-desktop production mode."""
    from unittest.mock import MagicMock, patch
    from app.core.security import security_headers

    mock_response = MagicMock()
    mock_response.headers = {}
    with patch("app.core.config.settings") as mock_settings, \
         patch("app.core.security.get_state_value", return_value=None):
        mock_settings.desktop_mode = False
        mock_settings.env = "production"
        mock_settings.strict_csp = False
        result = security_headers(mock_response)
    assert "Strict-Transport-Security" in result.headers

