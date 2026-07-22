# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_service import reconcile_client_balances, get_system_status


@pytest.mark.asyncio
async def test_reconcile_client_balances_conforme():
    # Mocking: Database query returns no discrepancies
    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result

    res = await reconcile_client_balances(mock_db)
    assert res["ok"] is True
    assert res["status"] == "Conforme"
    assert res["count"] == 0
    assert len(res["discrepancies"]) == 0


@pytest.mark.asyncio
async def test_reconcile_client_balances_discrepancy():
    # Mocking: Database query returns 1 discrepancy
    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    # Row columns: id, name, calculated_balance, view_balance, mv_balance
    mock_result.fetchall.return_value = [
        (42, "Client Mismatch", 15000.0, 15000.0, 12000.0)
    ]
    mock_db.execute.return_value = mock_result

    res = await reconcile_client_balances(mock_db)
    # The first query will detect discrepancy in mv_balance, trigger REFRESH and run again.
    # We let mock return discrepancy both times to simulate refresh failed to sync (e.g. mock returns same)
    assert res["ok"] is False
    assert res["status"] == "Ecart detecte"
    assert res["count"] == 1
    assert res["discrepancies"][0]["client_id"] == 42
    assert res["discrepancies"][0]["calculated"] == 15000.0
    assert res["discrepancies"][0]["materialized_view"] == 12000.0


@pytest.mark.asyncio
async def test_reconcile_client_balances_auto_heal():
    # In SQLite mode, view is dynamic and self-healing
    mock_db = MagicMock(spec=AsyncSession)
    mock_result_conforme = MagicMock()
    mock_result_conforme.fetchall.return_value = []

    mock_db.execute.return_value = mock_result_conforme

    res = await reconcile_client_balances(mock_db)
    assert res["ok"] is True
    assert res["status"] == "Conforme"
    assert res["count"] == 0


@pytest.mark.asyncio
async def test_reconcile_client_balances_exception():
    mock_db = MagicMock(spec=AsyncSession)
    mock_db.execute.side_effect = Exception("Query Timeout")

    res = await reconcile_client_balances(mock_db)
    assert res["ok"] is False
    assert res["status"] == "Erreur de verification"
    assert res["error"] == "Query Timeout"


@pytest.mark.asyncio
@patch("app.services.system_service.reconcile_client_balances")
@patch("app.services.system_service._probe_db_write")
@patch("app.services.system_service._probe_dir_write")
@patch("app.services.system_service.list_restore_backups")
@patch("app.services.system_service.get_pending_backup_marker")
async def test_get_system_status_includes_reconciliation(
    mock_pending, mock_backups, mock_probe_dir, mock_probe_db, mock_reconcile
):
    mock_reconcile.return_value = {"ok": True, "status": "Conforme", "count": 0, "discrepancies": []}
    mock_pending.return_value = {}
    mock_backups.return_value = []
    mock_probe_dir.return_value = {"ok": True, "status": "OK"}
    mock_probe_db.return_value = {"ok": True, "status": "OK"}

    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(c=5)
    mock_db.execute.return_value = mock_result

    status = await get_system_status(db=mock_db)
    assert "reconciliation" in status
    assert status["reconciliation"]["ok"] is True
