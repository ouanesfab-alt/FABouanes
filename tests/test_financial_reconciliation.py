# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.system_service import reconcile_client_balances, get_system_status


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
    # Mocking: First query returns mismatch, second query after refresh returns conforme
    mock_db = MagicMock(spec=AsyncSession)
    mock_result_mismatch = MagicMock()
    mock_result_mismatch.fetchall.return_value = [
        (42, "Client Mismatch", 15000.0, 15000.0, 12000.0)
    ]
    
    mock_result_conforme = MagicMock()
    mock_result_conforme.fetchall.return_value = []

    mock_db.execute.side_effect = [
        mock_result_mismatch,  # first select
        None,                  # refresh view stmt
        mock_result_conforme   # second select (post-refresh check)
    ]

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


from app.infra.perf_cache import clear_cache

@pytest.mark.asyncio
@patch("app.modules.admin.system_service.reconcile_client_balances")
@patch("app.modules.admin.system_service._probe_db_write")
@patch("app.modules.admin.system_service._probe_dir_write")
@patch("app.modules.admin.system_service.list_restore_backups")
@patch("app.modules.admin.system_service.get_pending_backup_marker")
async def test_get_system_status_includes_reconciliation(
    mock_pending, mock_backups, mock_probe_dir, mock_probe_db, mock_reconcile
):
    clear_cache()
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
    assert "financial_audit" in status


@pytest.mark.asyncio
async def test_reconcile_supplier_balances_conforme():
    from app.modules.accounting.service import reconcile_supplier_balances

    mock_db = MagicMock(spec=AsyncSession)
    mock_res_purchases = MagicMock()
    mock_res_purchases.all.return_value = [(1, "Fournisseur A", 10000.0)]
    mock_res_payments = MagicMock()
    mock_res_payments.all.return_value = [(1, 5000.0)]

    mock_db.execute.side_effect = [mock_res_purchases, mock_res_payments]

    res = await reconcile_supplier_balances(mock_db)
    assert res["ok"] is True
    assert res["status"] == "Conforme"
    assert res["count"] == 0


@pytest.mark.asyncio
async def test_reconcile_supplier_balances_discrepancy():
    from app.modules.accounting.service import reconcile_supplier_balances

    mock_db = MagicMock(spec=AsyncSession)
    # Purchased 2,000 but paid 5,000 -> excess payment of 3,000
    mock_res_purchases = MagicMock()
    mock_res_purchases.all.return_value = [(2, "Fournisseur B", 2000.0)]
    mock_res_payments = MagicMock()
    mock_res_payments.all.return_value = [(2, 5000.0)]

    mock_db.execute.side_effect = [mock_res_purchases, mock_res_payments]

    res = await reconcile_supplier_balances(mock_db)
    assert res["ok"] is False
    assert res["status"] == "Anomalie fournisseur détectée"
    assert res["count"] == 1
    assert res["discrepancies"][0]["supplier_id"] == 2
    assert res["discrepancies"][0]["balance_due"] == -3000.0


@pytest.mark.asyncio
async def test_reconcile_stock_balance():
    from decimal import Decimal
    from app.modules.accounting.service import reconcile_stock_balance

    mock_db = MagicMock(spec=AsyncSession)

    # 1st: Conforme case
    fp_mock = MagicMock(id=1, name="Produit Fini", stock_qty=Decimal("10.0"), avg_cost=Decimal("100.0"))
    rm_mock = MagicMock(id=2, name="Matière Première", stock_qty=Decimal("20.0"), avg_cost=Decimal("50.0"))

    res_fp = MagicMock()
    res_fp.scalars.return_value.all.return_value = [fp_mock]
    res_rm = MagicMock()
    res_rm.scalars.return_value.all.return_value = [rm_mock]

    mock_db.execute.side_effect = [res_fp, res_rm]
    res = await reconcile_stock_balance(mock_db)
    assert res["ok"] is True
    assert res["status"] == "Conforme"

    # 2nd: Anomalies case (negative stock + missing PMP)
    fp_bad = MagicMock(id=3, name="Produit Négatif", stock_qty=Decimal("-5.0"), avg_cost=Decimal("100.0"))
    rm_bad = MagicMock(id=4, name="Matière Sans PMP", stock_qty=Decimal("15.0"), avg_cost=Decimal("0.0"))

    res_fp_bad = MagicMock()
    res_fp_bad.scalars.return_value.all.return_value = [fp_bad]
    res_rm_bad = MagicMock()
    res_rm_bad.scalars.return_value.all.return_value = [rm_bad]

    mock_db.execute.side_effect = [res_fp_bad, res_rm_bad]
    res_anomalies = await reconcile_stock_balance(mock_db)
    assert res_anomalies["ok"] is False
    assert res_anomalies["count"] == 2
    assert any("Stock négatif" in d["anomaly"] for d in res_anomalies["discrepancies"])
    assert any("PMP" in d["anomaly"] for d in res_anomalies["discrepancies"])


@pytest.mark.asyncio
async def test_reconcile_scf_balance():
    from app.modules.accounting.service import reconcile_scf_balance

    mock_db = MagicMock(spec=AsyncSession)

    with patch("app.modules.accounting.scf_service.SCFService.get_balance_generale") as mock_bg:
        # Equilibré
        mock_bg.return_value = [
            {"compte": "512", "solde_debiteur": 15000.0, "solde_crediteur": 0.0},
            {"compte": "401", "solde_debiteur": 0.0, "solde_crediteur": 15000.0},
        ]
        res_ok = await reconcile_scf_balance(mock_db)
        assert res_ok["ok"] is True
        assert res_ok["status"] == "Conforme"
        assert res_ok["imbalance"] == 0.0

        # Déséquilibré
        mock_bg.return_value = [
            {"compte": "512", "solde_debiteur": 15000.0, "solde_crediteur": 0.0},
            {"compte": "401", "solde_debiteur": 0.0, "solde_crediteur": 12000.0},
        ]
        res_bad = await reconcile_scf_balance(mock_db)
        assert res_bad["ok"] is False
        assert res_bad["status"] == "Déséquilibre balance SCF"
        assert res_bad["imbalance"] == 3000.0


@pytest.mark.asyncio
async def test_reconcile_financial_system_and_assistant():
    from app.modules.accounting.service import AccountingService
    from app.modules.assistant.tool_actions_insights import handle_insights

    mock_db = MagicMock(spec=AsyncSession)

    with (
        patch("app.modules.admin.system_service.reconcile_client_balances") as m_cli,
        patch("app.modules.accounting.service.reconcile_supplier_balances") as m_sup,
        patch("app.modules.accounting.service.reconcile_stock_balance") as m_stk,
        patch("app.modules.accounting.service.reconcile_scf_balance") as m_scf,
    ):
        m_cli.return_value = {"ok": True, "count": 0, "discrepancies": []}
        m_sup.return_value = {"ok": True, "count": 0, "discrepancies": []}
        m_stk.return_value = {"ok": True, "count": 0, "discrepancies": []}
        m_scf.return_value = {"ok": True, "count": 0, "status": "Conforme", "discrepancies": []}

        system_res = await AccountingService.reconcile_financial_system(mock_db)
        assert system_res["ok"] is True
        assert system_res["total_anomalies"] == 0
        assert "✅" in system_res["summary"]

        # Test assistant call to run_financial_reconciliation
        from unittest.mock import AsyncMock
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        session_maker = MagicMock(return_value=mock_session_ctx)

        assistant_res = await handle_insights(
            func_name="run_financial_reconciliation",
            func_args={},
            session_maker=session_maker,
        )
        assert assistant_res is not None
        assert assistant_res["ok"] is True
        assert assistant_res["total_anomalies"] == 0
        assert "details" in assistant_res

