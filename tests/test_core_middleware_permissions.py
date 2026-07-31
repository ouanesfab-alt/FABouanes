"""Tests unitaires pour app/core/middleware.py et permissions.py (Vague 1.3 — couverture > 90%)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
import pytest
from fastapi import Request
from starlette.datastructures import Headers
from starlette.responses import Response

from app.core.middleware import CachedStaticFiles, RequestContextMiddleware
from app.core.permissions import (
    has_permission,
    normalize_role,
    _get_dynamic_permissions,
    _audit_permission_denied,
    permission_denied_response,
    require_permission,
    PERMISSION_AUDIT_READ,
    PERMISSION_SETTINGS_MANAGE,
)


@pytest.mark.asyncio
async def test_cached_static_files_headers():
    csf = CachedStaticFiles(directory="static")
    mock_resp = Response(content="static data", status_code=200)

    with mock.patch("starlette.staticfiles.StaticFiles.get_response", return_value=mock_resp):
        scope = {"type": "http", "method": "GET", "path": "/static/test.css", "headers": []}
        res = await csf.get_response("test.css", scope)
        assert res.status_code == 200
        assert "Cache-Control" in res.headers


@pytest.mark.asyncio
async def test_request_context_middleware_form_sanitization():
    middleware = RequestContextMiddleware(app=mock.MagicMock())

    async def mock_call_next(req):
        if hasattr(req, "form"):
            form_data = await req.form()
            assert "&lt;script&gt;" in form_data.get("clean")
        return Response("ok", status_code=200)


    scope = {
        "type": "http",
        "method": "POST",
        "path": "/form",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "session": {},
    }
    req = Request(scope)

    async def mock_form():
        from starlette.datastructures import FormData
        return FormData([("clean", "<script>clean_value</script>"), ("password", "secret123")])

    req.form = mock_form


    with mock.patch("app.core.middleware.ensure_csrf_token"), \
         mock.patch("app.core.middleware.load_user_from_session", return_value=None):
        res = await middleware.dispatch(req, mock_call_next)
        assert res.status_code == 200



def test_normalize_role():
    assert normalize_role("ADMIN") == "admin"
    assert normalize_role("user") == "operator"
    assert normalize_role(None) == "operator"


def test_get_dynamic_permissions():
    perms = _get_dynamic_permissions("admin")
    assert isinstance(perms, set)


def test_has_permission():
    assert has_permission(None, None) is True
    assert has_permission(None, PERMISSION_AUDIT_READ) is False

    admin_user = {"role": "admin", "custom_permissions": []}
    assert has_permission(admin_user, PERMISSION_SETTINGS_MANAGE) is True

    custom_user = {"role": "operator", "custom_permissions": [PERMISSION_AUDIT_READ]}
    assert has_permission(custom_user, PERMISSION_AUDIT_READ) is True


def test_permission_denied_response_unauthorized_api():
    mock_req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/test"))
    with mock.patch("app.core.permissions.get_state_value") as m_state:
        m_state.side_effect = lambda key: mock_req if key == "request" else None
        resp = permission_denied_response(PERMISSION_AUDIT_READ)
        assert resp.status_code == 401


def test_permission_denied_response_forbidden_api():
    mock_user = {"role": "operator"}
    mock_req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/test"), method="GET", scope={})

    with mock.patch("app.core.permissions.get_state_value") as m_state:
        m_state.side_effect = lambda key: mock_user if key == "user" else mock_req
        resp = permission_denied_response(PERMISSION_SETTINGS_MANAGE)
        assert resp.status_code == 403



def test_audit_permission_denied_exception_safe():
    with mock.patch("app.core.permissions.get_state_value", side_effect=Exception("State error")):
        _audit_permission_denied(PERMISSION_AUDIT_READ)


def test_require_permission_decorator():
    @require_permission(PERMISSION_AUDIT_READ)
    def dummy_view():
        return "success"

    mock_user = {"role": "admin"}
    with mock.patch("app.core.permissions.get_state_value", return_value=mock_user):
        res = dummy_view()
        assert res == "success"
