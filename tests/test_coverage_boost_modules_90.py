"""Tests unitaires ciblés pour propulser la couverture Python Core > 90%."""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
import pytest
from unittest import mock
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.exception_handlers import (
    is_html_request,
    not_found_handler,
    validation_handler,
    conflict_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.core.exceptions import NotFoundError, ValidationError, ConflictError
from app.modules.assistant.rag import normalize_text, search_manual
from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql
from app.modules.assistant.sql_tools import serialize_for_json, dry_run_sql


def test_is_html_request():
    req_api = mock.MagicMock(spec=Request)
    req_api.url.path = "/api/v1/sales"
    assert is_html_request(req_api) is False

    req_json = mock.MagicMock(spec=Request)
    req_json.url.path = "/dashboard"
    req_json.headers = {"accept": "application/json"}
    assert is_html_request(req_json) is False

    req_html = mock.MagicMock(spec=Request)
    req_html.url.path = "/dashboard"
    req_html.headers = {"accept": "text/html,application/xhtml+xml"}
    assert is_html_request(req_html) is True


@pytest.mark.asyncio
async def test_exception_handlers_json():
    req_api = mock.MagicMock(spec=Request)
    req_api.url.path = "/api/v1/clients"
    req_api.headers = {"accept": "application/json"}

    nf_res = await not_found_handler(req_api, NotFoundError("client", 123))
    assert isinstance(nf_res, JSONResponse)
    assert nf_res.status_code == 404

    val_res = await validation_handler(req_api, ValidationError("champ requis"))
    assert isinstance(val_res, JSONResponse)
    assert val_res.status_code == 422

    conf_res = await conflict_handler(req_api, ConflictError("doublon"))
    assert isinstance(conf_res, JSONResponse)
    assert conf_res.status_code == 409

    http_res = await http_exception_handler(req_api, HTTPException(status_code=403, detail="Interdit"))
    assert isinstance(http_res, JSONResponse)
    assert http_res.status_code == 403

    unh_res = await unhandled_exception_handler(req_api, ValueError("valeur invalide"))
    assert isinstance(unh_res, JSONResponse)
    assert unh_res.status_code == 400


def test_rag_helpers():
    norm = normalize_text("Vente de ciment 50kg pour client Lamine")
    assert "vente" in norm
    results = search_manual("facture vente", limit=2)
    assert isinstance(results, list)


def test_sql_guard_validations():
    read_res = validate_readonly_sql("SELECT count(*) FROM clients")
    assert read_res.ok is True

    drop_res = validate_readonly_sql("DROP TABLE clients")
    assert drop_res.ok is False

    write_res = validate_write_sql("UPDATE clients SET notes = 'test' WHERE id = 1")
    assert write_res is not None


def test_serialize_for_json_and_dry_run():
    data = {
        "amount": Decimal("100.50"),
        "int_dec": Decimal("50.00"),
        "dt": datetime(2026, 1, 1, 12, 0, 0),
        "d": date(2026, 1, 1),
        "list": [Decimal("10.00")],
    }
    serialized = serialize_for_json(data)
    assert serialized["amount"] == 100.50
    assert serialized["int_dec"] == 50
    assert serialized["d"] == "2026-01-01"

    dry_res = dry_run_sql("DROP TABLE clients")
    assert "refusée" in dry_res or "⚠️" in dry_res
