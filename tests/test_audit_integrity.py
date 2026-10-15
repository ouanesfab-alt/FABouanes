# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import (
    compute_audit_signature,
    verify_audit_log_integrity,
    audit_event,
    _get_audit_queue,
)


def test_compute_audit_signature_deterministic():
    payload = "admin:create:client:10:success:None:{\"name\": \"ABC\"}"
    sig1 = compute_audit_signature(payload)
    sig2 = compute_audit_signature(payload)
    assert len(sig1) == 64
    assert sig1 == sig2

    # Different payload yields different signature
    diff_payload = "admin:update:client:10:success:None:{\"name\": \"ABC\"}"
    assert compute_audit_signature(diff_payload) != sig1


def test_audit_event_embeds_signature():
    queue = _get_audit_queue()
    # Empty queue for clean test
    while not queue.empty():
        queue.get_nowait()

    audit_event(
        action="update_price",
        entity_type="product",
        entity_id=99,
        status="success",
        before={"price": 100},
        after={"price": 150},
        meta={"source": "unit_test"},
    )

    assert not queue.empty()
    item = queue.get_nowait()
    meta_json_str = item[13]
    meta = json.loads(meta_json_str)

    assert "_audit_sig" in meta
    assert len(meta["_audit_sig"]) == 64


@pytest.mark.asyncio
async def test_verify_audit_log_integrity_valid():
    actor = "operator"
    action = "sale_create"
    entity_type = "sale"
    entity_id = "123"
    status = "success"
    before = None
    after = json.dumps({"total": 5000.0})

    sig_payload = f"{actor}:{action}:{entity_type}:{entity_id}:{status}:{before}:{after}"
    valid_sig = compute_audit_signature(sig_payload)
    meta = json.dumps({"_audit_sig": valid_sig, "note": "ok"})

    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (1, actor, action, entity_type, entity_id, status, before, after, meta, "2026-10-15 10:00:00")
    ]
    mock_db.execute.return_value = mock_result

    res = await verify_audit_log_integrity(limit=50, db=mock_db)
    assert res["ok"] is True
    assert res["status"] == "Intègre"
    assert res["verified_count"] == 1
    assert res["tampered_count"] == 0
    assert res["unsigned_count"] == 0


@pytest.mark.asyncio
async def test_verify_audit_log_integrity_tampered():
    actor = "operator"
    action = "sale_create"
    entity_type = "sale"
    entity_id = "123"
    status = "success"
    before = None
    after = json.dumps({"total": 5000.0})

    # Legitimate signature for 5000.0
    sig_payload = f"{actor}:{action}:{entity_type}:{entity_id}:{status}:{before}:{after}"
    legit_sig = compute_audit_signature(sig_payload)
    meta = json.dumps({"_audit_sig": legit_sig})

    # Attacker alters 'after' in database directly to 500.0 without regenerating HMAC
    tampered_after = json.dumps({"total": 500.0})

    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        (1, actor, action, entity_type, entity_id, status, before, tampered_after, meta, "2026-10-15 10:00:00")
    ]
    mock_db.execute.return_value = mock_result

    res = await verify_audit_log_integrity(limit=50, db=mock_db)
    assert res["ok"] is False
    assert res["status"] == "Altération détectée"
    assert res["verified_count"] == 0
    assert res["tampered_count"] == 1
    assert len(res["tampered_records"]) == 1
    assert res["tampered_records"][0]["id"] == 1


@pytest.mark.asyncio
async def test_verify_audit_log_integrity_unsigned_and_malformed():
    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        # Unsigned legacy row (no meta)
        (1, "admin", "login", "user", "1", "success", None, None, None, "2026-10-15 10:00:00"),
        # Meta without signature
        (2, "admin", "login", "user", "1", "success", None, None, "{}", "2026-10-15 10:01:00"),
        # Corrupted meta json
        (3, "admin", "login", "user", "1", "success", None, None, "{invalid_json", "2026-10-15 10:02:00"),
    ]
    mock_db.execute.return_value = mock_result

    res = await verify_audit_log_integrity(limit=50, db=mock_db)
    assert res["unsigned_count"] == 2
    assert res["tampered_count"] == 1
    assert res["ok"] is False
