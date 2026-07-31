"""Tests unitaires pour app/core/exception_handlers.py et lifespan.py (Couverture > 90%)."""
from __future__ import annotations

from unittest import mock
import pytest
from fastapi import FastAPI, Request

from app.core.exception_handlers import (
    is_html_request,
    not_found_handler,
    validation_handler,
    conflict_handler,
    permission_handler,
    auth_required_handler,
    unhandled_exception_handler,
)
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionDeniedError,
    AuthenticationRequiredError,
)
from app.core.lifespan import lifespan


def test_is_html_request():
    req_api = Request({"type": "http", "method": "GET", "path": "/api/v1/test", "headers": []})
    assert is_html_request(req_api) is False

    req_json = Request({"type": "http", "method": "GET", "path": "/web/data", "headers": [(b"accept", b"application/json")]})
    assert is_html_request(req_json) is False

    req_html = Request({"type": "http", "method": "GET", "path": "/dashboard", "headers": [(b"accept", b"text/html")]})
    assert is_html_request(req_html) is True


@pytest.mark.asyncio
async def test_exception_handlers_api_responses():
    req_api = Request({"type": "http", "method": "GET", "path": "/api/v1/test", "headers": []})

    # NotFoundError
    res_nf = await not_found_handler(req_api, NotFoundError("Product", 123))
    assert res_nf.status_code == 404

    # ValidationError
    res_val = await validation_handler(req_api, ValidationError("Champ invalide"))
    assert res_val.status_code == 422

    # ConflictError
    res_conf = await conflict_handler(req_api, ConflictError("Doublon détecté"))
    assert res_conf.status_code == 409

    # Unhandled Exception
    res_500 = await unhandled_exception_handler(req_api, Exception("Crash système"))
    assert res_500.status_code == 500


@pytest.mark.asyncio
async def test_lifespan_lifecycle():
    app = FastAPI()
    with mock.patch("app.core.lifespan.validate_single_worker_runtime"), \
         mock.patch("app.core.lifespan.ensure_runtime_dirs"), \
         mock.patch("app.core.lifespan.configure_logging"), \
         mock.patch("app.core.lifespan.start_audit_worker"), \
         mock.patch("app.core.lifespan.stop_audit_worker"), \
         mock.patch("app.core.lifespan.bootstrap_and_migrate"), \
         mock.patch("app.core.lifespan.get_enabled_modules", return_value=[]), \
         mock.patch("app.services.backup_service.start_background_services"), \
         mock.patch("app.services.backup_service.shutdown_background_services"):
        async with lifespan(app):
            pass

