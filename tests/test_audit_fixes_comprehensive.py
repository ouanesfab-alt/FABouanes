import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.core.security import client_ip
from app.core.auth_cookie import build_auth_cookie_value, read_auth_cookie_payload, read_auth_cookie_value
from app.core.jwt_auth import require_mobile_permission


def test_client_ip_trusted_proxy():
    # Mock untrusted proxy
    req_mock = MagicMock()
    req_mock.client.host = "192.168.1.100"
    req_mock.headers = {"X-Forwarded-For": "203.0.113.195"}

    with patch("app.core.security._TRUSTED_PROXIES", frozenset(["10.0.0.1"])):
        # Untrusted direct ip -> must NOT use X-Forwarded-For
        assert client_ip(req_mock) == "192.168.1.100"

    with patch("app.core.security._TRUSTED_PROXIES", frozenset(["192.168.1.100"])):
        # Trusted direct ip -> uses X-Forwarded-For
        assert client_ip(req_mock) == "203.0.113.195"


def test_auth_cookie_expiration_and_payload():
    # Valid cookie with future exp
    val = build_auth_cookie_value(user_id=42, fingerprint="fp123", max_age=3600)
    payload = read_auth_cookie_payload(val, current_fingerprint="fp123")
    assert payload is not None
    assert payload["user_id"] == 42
    assert read_auth_cookie_value(val, current_fingerprint="fp123") == 42

    # Expired cookie
    expired_val = build_auth_cookie_value(user_id=42, fingerprint="fp123", max_age=-10)
    assert read_auth_cookie_payload(expired_val, current_fingerprint="fp123") is None
    assert read_auth_cookie_value(expired_val, current_fingerprint="fp123") is None


def test_mobile_permissions_dependency():
    from app.core.permissions import PERMISSION_USERS_MANAGE

    dep = require_mobile_permission(PERMISSION_USERS_MANAGE)

    # Admin has users.manage
    with patch("app.core.db_helpers.query_db") as mock_query:
        mock_query.return_value = {"id": 1, "role": "admin", "is_active": True}
        res = dep(user_id=1)
        assert res["id"] == 1

        mock_query.return_value = {"id": 2, "role": "operator", "is_active": True, "custom_permissions_json": "[]"}
        with pytest.raises(HTTPException) as exc:
            dep(user_id=2)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_offline_purchase_permission_error_not_saved_as_500():
    from app.api.v1.offline import sync_operation
    from fastapi import Request

    req = MagicMock(spec=Request)
    req.headers = {"X-Idempotency-Key": "test-key-1"}
    req.json = MagicMock()

    async def mock_json():
        return {"type": "create_purchase", "payload": {}}

    req.json.side_effect = mock_json

    # Operator role should fail on create_purchase with 403, and NOT store 500
    with patch("app.api.v1.offline.require_api_user") as mock_req_user:
        # First call for PERMISSION_OPERATIONS_WRITE succeeds
        # Second call for "admin" raises 403
        mock_req_user.side_effect = [None, HTTPException(status_code=403, detail="Accès réservé aux administrateurs")]

        with patch("app.api.v1.offline.check_idempotency", return_value=None):
            with patch("app.api.v1.offline.save_idempotency") as mock_save:
                with pytest.raises(HTTPException) as exc:
                    await sync_operation(req, db=MagicMock())

                assert exc.value.status_code == 403
                # Verification: save_idempotency was NEVER called with 500
                mock_save.assert_not_called()


def test_atomic_refresh_token_rotation():
    from app.core.jwt_auth import create_refresh_token, rotate_mobile_refresh_token

    with patch("app.core.db_helpers.execute_db"):
        token = create_refresh_token(user_id=10)

    with patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:
        with patch("app.core.db_helpers.execute_db") as mock_exec:
            with patch("app.core.db_helpers.query_db") as mock_query:
                # 1st query: api_refresh_tokens lookup
                # 2nd query: users lookup in validate_mobile_refresh_token
                # 3rd query: users lookup in rotate_mobile_refresh_token
                mock_query.side_effect = [
                    {"id": 123, "user_id": 10, "revoked_at": None},
                    {"id": 10, "is_active": True},
                    {"id": 10, "username": "testuser", "role": "operator", "is_active": True},
                ]
                user, new_token = rotate_mobile_refresh_token(token)
                assert user["id"] == 10
                assert user["role"] == "operator"
                assert new_token != token
                mock_tx.assert_called_once()
                # Verify revocation update was executed
                assert any("UPDATE api_refresh_tokens SET revoked_at" in str(c) for c in mock_exec.call_args_list)
                # Verify new token insertion was executed
                assert any("INSERT INTO api_refresh_tokens" in str(c) for c in mock_exec.call_args_list)
