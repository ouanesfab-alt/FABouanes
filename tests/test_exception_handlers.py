import pytest
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from unittest import mock

from app.core.exception_handlers import (
    is_html_request,
    not_found_handler,
    validation_handler,
    conflict_handler,
    permission_handler,
    auth_required_handler,
    http_exception_handler,
)
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionDeniedError,
    AuthenticationRequiredError,
)

def create_mock_request(path: str, headers: dict = None) -> Request:
    mock_req = mock.MagicMock(spec=Request)
    mock_req.url = mock.MagicMock()
    mock_req.url.path = path
    mock_req.headers = headers or {}
    mock_req.scope = {"route": None, "endpoint_name": ""}
    return mock_req

def test_is_html_request():
    # API path should not be HTML
    req = create_mock_request("/api/sales")
    assert is_html_request(req) is False

    # HTML accept header
    req = create_mock_request("/sales", {"accept": "text/html,application/xhtml+xml"})
    assert is_html_request(req) is True

    # JSON accept header without HTML
    req = create_mock_request("/sales", {"accept": "application/json"})
    assert is_html_request(req) is False

@pytest.mark.asyncio
async def test_not_found_handler():
    exc = NotFoundError("Sale", 42)
    
    # API request
    req = create_mock_request("/api/sales/42")
    res = await not_found_handler(req, exc)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 404
    
    # HTML request
    req = create_mock_request("/sales/42", {"accept": "text/html"})
    with mock.patch("app.web.deps.templates.TemplateResponse") as mock_tmpl, \
         mock.patch("app.web.deps.template_context") as mock_ctx:
        mock_tmpl.return_value = "html-response"
        mock_ctx.return_value = {}
        res = await not_found_handler(req, exc)
        assert res == "html-response"
        mock_tmpl.assert_called_once()

@pytest.mark.asyncio
async def test_validation_handler():
    exc = ValidationError("Invalid quantity", "qty")
    
    # API request
    req = create_mock_request("/api/sales")
    res = await validation_handler(req, exc)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 422
    
    # HTML request
    req = create_mock_request("/sales", {"accept": "text/html"})
    with mock.patch("app.web.deps.templates.TemplateResponse") as mock_tmpl, \
         mock.patch("app.web.deps.template_context") as mock_ctx:
        mock_tmpl.return_value = "html-response"
        mock_ctx.return_value = {}
        res = await validation_handler(req, exc)
        assert res == "html-response"

@pytest.mark.asyncio
async def test_conflict_handler():
    exc = ConflictError("Out of stock", {"available": 5})
    
    # API request
    req = create_mock_request("/api/sales")
    res = await conflict_handler(req, exc)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 409
    
    # HTML request
    req = create_mock_request("/sales", {"accept": "text/html"})
    with mock.patch("app.web.deps.templates.TemplateResponse") as mock_tmpl, \
         mock.patch("app.web.deps.template_context") as mock_ctx:
        mock_tmpl.return_value = "html-response"
        mock_ctx.return_value = {}
        res = await conflict_handler(req, exc)
        assert res == "html-response"

@pytest.mark.asyncio
async def test_permission_handler():
    exc = PermissionDeniedError("insufficient_funds")
    req = create_mock_request("/api/sales")
    
    with mock.patch("app.core.permissions.permission_denied_response") as mock_denied:
        mock_denied.return_value = "denied-response"
        res = await permission_handler(req, exc)
        assert res == "denied-response"
        mock_denied.assert_called_once_with("permission_denied")

@pytest.mark.asyncio
async def test_auth_required_handler():
    exc = AuthenticationRequiredError()
    req = create_mock_request("/api/sales")
    
    with mock.patch("app.core.permissions.permission_denied_response") as mock_denied:
        mock_denied.return_value = "denied-response"
        res = await auth_required_handler(req, exc)
        assert res == "denied-response"
        mock_denied.assert_called_once_with(None)

@pytest.mark.asyncio
async def test_http_exception_handler():
    # API requests
    req = create_mock_request("/api/test")
    
    # Simple string detail
    exc = HTTPException(status_code=400, detail="Malformed payload")
    res = await http_exception_handler(req, exc)
    assert isinstance(res, JSONResponse)
    assert res.status_code == 400
    
    # Dict detail
    exc_dict = HTTPException(status_code=403, detail={"code": "custom_err", "message": "Custom block"})
    res_dict = await http_exception_handler(req, exc_dict)
    assert res_dict.status_code == 403

    # HTML request
    req_html = create_mock_request("/test", {"accept": "text/html"})
    with mock.patch("app.web.deps.templates.TemplateResponse") as mock_tmpl, \
         mock.patch("app.web.deps.template_context") as mock_ctx:
        mock_tmpl.return_value = "html-response"
        mock_ctx.return_value = {}
        res_html = await http_exception_handler(req_html, exc)
        assert res_html == "html-response"
