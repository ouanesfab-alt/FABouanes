"""Tests de couverture ciblés — Lot 2.

Couvre: history.py, exception_handlers.py, production models validators
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch


# ── history.py (77% → target 100%) ─────────────────────────────────


def test_get_last_user_query_from_parts():
    """Extract last user query from parts format."""
    from app.modules.assistant.history import get_last_user_query

    messages = [
        {"role": "user", "parts": [{"text": "bonjour"}]},
        {"role": "model", "parts": [{"text": "salut!"}]},
        {"role": "user", "parts": [{"text": "montre moi"}, {"text": "les ventes"}]},
    ]
    result = get_last_user_query(messages)
    assert "montre moi" in result
    assert "les ventes" in result


def test_get_last_user_query_from_content():
    """Extract last user query from content format (non-list parts)."""
    from app.modules.assistant.history import get_last_user_query

    messages = [
        {"role": "user", "parts": "some string", "content": "quel est le stock?"},
    ]
    result = get_last_user_query(messages)
    assert result == "quel est le stock?"


def test_get_last_user_query_empty():
    """Empty messages returns empty string."""
    from app.modules.assistant.history import get_last_user_query
    assert get_last_user_query([]) == ""


def test_get_last_user_query_no_user():
    """Messages with no user role returns empty string."""
    from app.modules.assistant.history import get_last_user_query
    messages = [{"role": "model", "parts": [{"text": "salut"}]}]
    assert get_last_user_query(messages) == ""


def test_clean_unconfirmed_tool_calls_normal():
    """Normal messages pass through unchanged."""
    from app.modules.assistant.history import clean_unconfirmed_tool_calls

    messages = [
        {"role": "user", "parts": [{"text": "hello"}]},
        {"role": "model", "parts": [{"text": "hi!"}]},
    ]
    result = clean_unconfirmed_tool_calls(messages)
    assert len(result) == 2


def test_clean_unconfirmed_tool_calls_with_response():
    """Tool call with function response is kept."""
    from app.modules.assistant.history import clean_unconfirmed_tool_calls

    messages = [
        {"role": "model", "parts": [{"functionCall": {"name": "get_stock"}}]},
        {"role": "function", "parts": [{"text": "stock: 50"}]},
    ]
    result = clean_unconfirmed_tool_calls(messages)
    assert len(result) == 2


def test_clean_unconfirmed_tool_calls_dangling_with_text():
    """Dangling tool call with text parts keeps text only."""
    from app.modules.assistant.history import clean_unconfirmed_tool_calls

    messages = [
        {"role": "model", "parts": [
            {"text": "Je vais vérifier"},
            {"functionCall": {"name": "check_stock"}},
        ]},
    ]
    result = clean_unconfirmed_tool_calls(messages)
    assert len(result) == 1
    assert "text" in result[0]["parts"][0]
    assert not any("functionCall" in p for p in result[0]["parts"])


def test_clean_unconfirmed_tool_calls_dangling_no_text():
    """Dangling tool call with no text is removed entirely."""
    from app.modules.assistant.history import clean_unconfirmed_tool_calls

    messages = [
        {"role": "model", "parts": [{"functionCall": {"name": "check_stock"}}]},
    ]
    result = clean_unconfirmed_tool_calls(messages)
    assert len(result) == 0


def test_clean_unconfirmed_tool_calls_via_tool_calls_key():
    """Dangling tool call via 'tool_calls' key (OpenAI format) is removed."""
    from app.modules.assistant.history import clean_unconfirmed_tool_calls

    messages = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "test"}}], "parts": "blah"},
    ]
    result = clean_unconfirmed_tool_calls(messages)
    # Should be removed (no function response follows, and parts is not a list)
    assert len(result) == 0


# ── exception_handlers.py (76% → target ~88%) ──────────────────────


def test_is_html_request_api_path():
    """API paths should not be treated as HTML requests."""
    from app.core.exception_handlers import is_html_request
    request = MagicMock()
    request.url.path = "/api/v1/stock"
    request.headers = {"accept": "text/html"}
    assert is_html_request(request) is False


def test_is_html_request_json_accept():
    """JSON accept header should not be treated as HTML request."""
    from app.core.exception_handlers import is_html_request
    request = MagicMock()
    request.url.path = "/dashboard"
    request.headers = {"accept": "application/json"}
    assert is_html_request(request) is False


def test_is_html_request_html_accept():
    """HTML accept header on non-API path is HTML request."""
    from app.core.exception_handlers import is_html_request
    request = MagicMock()
    request.url.path = "/dashboard"
    request.headers = {"accept": "text/html"}
    assert is_html_request(request) is True


@pytest.mark.asyncio
async def test_not_found_handler_api():
    """NotFoundError returns 404 JSON for API requests."""
    from app.core.exception_handlers import not_found_handler
    from app.core.exceptions import NotFoundError

    request = MagicMock()
    request.url.path = "/api/v1/clients/999"
    request.headers = {"accept": "application/json"}

    exc = NotFoundError("client", 999)
    response = await not_found_handler(request, exc)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_validation_handler_api():
    """ValidationError returns 422 JSON for API requests."""
    from app.core.exception_handlers import validation_handler
    from app.core.exceptions import ValidationError

    request = MagicMock()
    request.url.path = "/api/v1/sales"
    request.headers = {"accept": "application/json"}

    exc = ValidationError("Montant invalide", field="amount")
    response = await validation_handler(request, exc)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_conflict_handler_api():
    """ConflictError returns 409 JSON for API requests."""
    from app.core.exception_handlers import conflict_handler
    from app.core.exceptions import ConflictError

    request = MagicMock()
    request.url.path = "/api/v1/products"
    request.headers = {"accept": "application/json"}

    exc = ConflictError("Ce produit existe déjà")
    response = await conflict_handler(request, exc)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_http_exception_handler_api_dict_detail():
    """HTTPException with dict detail returns structured JSON."""
    from app.core.exception_handlers import http_exception_handler
    from fastapi import HTTPException

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "GET"

    exc = HTTPException(status_code=403, detail={"code": "forbidden", "message": "Accès refusé"})
    response = await http_exception_handler(request, exc)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_http_exception_handler_api_string_detail():
    """HTTPException with string detail returns string message JSON."""
    from app.core.exception_handlers import http_exception_handler
    from fastapi import HTTPException

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "GET"

    exc = HTTPException(status_code=500, detail="Erreur serveur")
    response = await http_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_handler_foreign_key():
    """Foreign key violation returns friendly message."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/products/1"
    request.headers = {"accept": "application/json"}
    request.method = "DELETE"

    exc = Exception("violates foreign key constraint on table X")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_handler_unique_constraint():
    """Unique constraint violation returns friendly message."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/products"
    request.headers = {"accept": "application/json"}
    request.method = "POST"

    exc = Exception("duplicate key value violates unique constraint")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_handler_connection_error():
    """Connection error returns friendly DB reset message."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "GET"

    exc = Exception("OperationalError: could not connect to server")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_handler_generic():
    """Generic exception returns internal error message."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "GET"

    exc = RuntimeError("something unexpected")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_handler_numeric_out_of_range():
    """Numeric out of range returns friendly message."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "POST"

    exc = Exception("numeric value out of range for column amount")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_unhandled_exception_broken_pipe():
    """Broken pipe returns 200 disconnected status."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "GET"

    exc = ConnectionResetError("connection reset by peer")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_unhandled_exception_valueerror_api():
    """ValueError returns 400 for API requests."""
    from app.core.exception_handlers import unhandled_exception_handler

    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.headers = {"accept": "application/json"}
    request.method = "POST"

    exc = ValueError("invalid input format")
    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 400


# ── production models validators (78% → target ~95%) ───────────────


def test_production_batch_coerce_date_from_string():
    """ProductionBatch._coerce_production_date converts ISO string to date."""
    from app.core.models_pkg.production import ProductionBatch
    result = ProductionBatch._coerce_production_date("2025-06-15")
    from datetime import date
    assert result == date(2025, 6, 15)


def test_production_batch_coerce_date_passthrough():
    """ProductionBatch._coerce_production_date passes date objects through."""
    from app.core.models_pkg.production import ProductionBatch
    from datetime import date
    d = date(2025, 1, 1)
    assert ProductionBatch._coerce_production_date(d) is d


def test_production_batch_coerce_decimals_none():
    """ProductionBatch._coerce_decimals returns 0.00 for None."""
    from app.core.models_pkg.production import ProductionBatch
    result = ProductionBatch._coerce_decimals(None)
    assert result == Decimal("0.00")


def test_production_batch_coerce_decimals_float():
    """ProductionBatch._coerce_decimals converts float to Decimal."""
    from app.core.models_pkg.production import ProductionBatch
    result = ProductionBatch._coerce_decimals(12.5)
    assert result == Decimal("12.5")


def test_production_batch_coerce_decimals_string():
    """ProductionBatch._coerce_decimals converts string to Decimal."""
    from app.core.models_pkg.production import ProductionBatch
    result = ProductionBatch._coerce_decimals("99.99")
    assert result == Decimal("99.99")


def test_production_batch_item_coerce_decimals():
    """ProductionBatchItem._coerce_decimals works for None, float, str."""
    from app.core.models_pkg.production import ProductionBatchItem
    assert ProductionBatchItem._coerce_decimals(None) == Decimal("0.00")
    assert ProductionBatchItem._coerce_decimals(5.5) == Decimal("5.5")
    assert ProductionBatchItem._coerce_decimals(Decimal("10")) == Decimal("10")


def test_saved_recipe_item_coerce_decimals():
    """SavedRecipeItem._coerce_decimals works for None, float, str."""
    from app.core.models_pkg.production import SavedRecipeItem
    assert SavedRecipeItem._coerce_decimals(None) == Decimal("0.00")
    assert SavedRecipeItem._coerce_decimals(2.75) == Decimal("2.75")
    assert SavedRecipeItem._coerce_decimals(Decimal("100")) == Decimal("100")
