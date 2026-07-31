"""Tests unitaires pour app/modules/accounting/scf_service.py (Phase 3.1)."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from app.modules.accounting.scf_service import SCFService


def test_get_plan_comptable():
    plan = SCFService.get_plan_comptable()
    assert isinstance(plan, list)
    assert len(plan) > 0
    codes = [item["code"] for item in plan]
    assert "700" in codes
    assert "530" in codes


@pytest.mark.asyncio
async def test_get_balance_generale():
    def mock_query_db(sql: str, one: bool = True):
        if "sales" in sql and "raw_sales" not in sql:
            return {"total": 5000.0}
        if "raw_sales" in sql:
            return {"total": 2000.0}
        if "purchases" in sql:
            return {"total": 3000.0}
        if "payments" in sql:
            return {"total": 4000.0}
        if "expenses" in sql:
            return {"total": 500.0}
        if "clients_with_stats" in sql:
            return {"total_debt": 1500.0}
        if "raw_materials" in sql:
            return {"val": 1000.0}
        if "finished_products" in sql:
            return {"val": 2500.0}
        return {"total": 0.0, "val": 0.0, "total_debt": 0.0}

    with patch("app.modules.accounting.scf_service.query_db", side_effect=mock_query_db):
        balance = await SCFService.get_balance_generale()
        assert isinstance(balance, list)
        assert len(balance) == 8

        codes = {item["code"]: item for item in balance}
        assert codes["700"]["credit"] == 5000.0
        assert codes["707"]["credit"] == 2000.0
        assert codes["600"]["debit"] == 3000.0
        assert codes["530"]["debit"] == 3500.0  # 4000 encaisse - 500 depenses


@pytest.mark.asyncio
async def test_get_tcr_and_bilan():
    mock_balance = [
        {"code": "300", "debit": 1000.0, "credit": 0.0, "solde_debiteur": 1000.0, "solde_crediteur": 0.0},
        {"code": "355", "debit": 2000.0, "credit": 0.0, "solde_debiteur": 2000.0, "solde_crediteur": 0.0},
        {"code": "411", "debit": 1500.0, "credit": 0.0, "solde_debiteur": 1500.0, "solde_crediteur": 0.0},
        {"code": "401", "debit": 0.0, "credit": 500.0, "solde_debiteur": 0.0, "solde_crediteur": 500.0},
        {"code": "530", "debit": 3000.0, "credit": 0.0, "solde_debiteur": 3000.0, "solde_crediteur": 0.0},
        {"code": "600", "debit": 4000.0, "credit": 0.0, "solde_debiteur": 4000.0, "solde_crediteur": 0.0},
        {"code": "629", "debit": 500.0, "credit": 0.0, "solde_debiteur": 500.0, "solde_crediteur": 0.0},
        {"code": "700", "debit": 0.0, "credit": 8000.0, "solde_debiteur": 0.0, "solde_crediteur": 8000.0},
    ]

    with patch.object(SCFService, "get_balance_generale", return_value=mock_balance):
        tcr = await SCFService.get_tcr()
        assert tcr["chiffre_affaires"] == 8000.0
        assert tcr["achats_consommes"] == 4000.0
        assert tcr["marge_brute"] == 4000.0
        assert tcr["resultat_net"] == 3500.0

        bilan = await SCFService.get_bilan()
        assert "actif" in bilan
        assert "passif" in bilan
        assert bilan["actif"]["total"] == 7500.0  # 3000 (stocks) + 1500 (creances) + 3000 (tresorerie)
