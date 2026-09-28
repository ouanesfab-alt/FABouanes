from __future__ import annotations

import pytest

from app.utils.api_response import APIResponse
from app.utils.pagination import (
    paginate_sequence,
    pagination_context,
    pagination_meta,
    parse_pagination,
)
from app.utils.phone_normalize import normalize_phone_number


def test_normalize_phone_number_empty():
    assert normalize_phone_number("") == ""
    assert normalize_phone_number(None) == ""


def test_normalize_phone_number_algerian():
    # Avec 00213
    assert normalize_phone_number("00213555123456") == "+213555123456"
    # Avec préfixe 0 local (05, 06, 07, etc.)
    assert normalize_phone_number("0550123456") == "+213550123456"
    assert normalize_phone_number("0661987654") == "+213661987654"
    assert normalize_phone_number("0770001122") == "+213770001122"
    # Format sans préfixe 9 chiffres
    assert normalize_phone_number("550123456") == "+213550123456"
    # Format 213 sans plus
    assert normalize_phone_number("213550123456") == "+213550123456"
    # Déjà formaté avec +
    assert normalize_phone_number("+213550123456") == "+213550123456"
    # Avec espaces et tirets
    assert normalize_phone_number("05 50-12 34 56") == "+213550123456"


def test_api_response_success():
    resp = APIResponse.success(data={"id": 1, "name": "Produit A"}, message="OK")
    assert resp.status_code == 200
    import json
    body = json.loads(resp.body)
    assert body["success"] is True
    assert body["ok"] is True
    assert body["message"] == "OK"
    assert body["data"]["name"] == "Produit A"


def test_api_response_error():
    resp = APIResponse.error("Introuvable", status_code=404, errors=["id non existant"])
    assert resp.status_code == 404
    import json
    body = json.loads(resp.body)
    assert body["success"] is False
    assert body["ok"] is False
    assert body["error"] == "Introuvable"
    assert body["errors"] == ["id non existant"]


def test_pagination_meta():
    meta = pagination_meta(total=55, page=1, page_size=20)
    assert meta["total"] == 55
    assert meta["page"] == 1
    assert meta["page_size"] == 20
    assert meta["total_pages"] == 3
    assert meta["has_next"] is True
    assert meta["has_prev"] is False

    meta_last = pagination_meta(total=55, page=3, page_size=20)
    assert meta_last["has_next"] is False
    assert meta_last["has_prev"] is True


def test_parse_pagination():
    page, page_size, offset = parse_pagination({"page": "2", "page_size": "10"})
    assert page == 2
    assert page_size == 10
    assert offset == 10

    # Test valeurs par défaut et résilience
    page_def, size_def, off_def = parse_pagination({})
    assert page_def == 1
    assert size_def == 25
    assert off_def == 0


def test_paginate_sequence():
    items = list(range(50))
    args = {"page": 2, "page_size": 10}
    sliced, ctx = paginate_sequence(items, args, path="/test")
    assert sliced == list(range(10, 20))
    assert ctx["page"] == 2
    assert ctx["total"] == 50
    assert ctx["pages"] == 5
    assert ctx["has_prev"] is True
    assert ctx["has_next"] is True


def test_pagination_context():
    ctx = pagination_context("/articles", {"search": "test"}, total=100, page=2, page_size=20)
    assert ctx["page"] == 2
    assert ctx["pages"] == 5
    assert ctx["total"] == 100
    assert ctx["start"] == 21
    assert ctx["end"] == 40
    assert "page=1" in ctx["prev_url"]
    assert "page=3" in ctx["next_url"]


@pytest.mark.asyncio
async def test_create_client_duplicate_rejected():
    from unittest.mock import AsyncMock
    from app.modules.clients.service import ClientService
    from app.modules.clients.schemas_validation import ClientCreateSchema
    from app.core.exceptions import ConflictError
    from app.core.models import Client

    mock_session = AsyncMock()
    service = ClientService(mock_session)
    service.repo.find_by_name = AsyncMock(return_value=Client(id=1, name="Client Existant"))

    schema = ClientCreateSchema(name="Client Existant", phone="0550112233")
    with pytest.raises(ConflictError) as exc_info:
        await service.create_client(schema)

    assert "existe déjà" in str(exc_info.value)

