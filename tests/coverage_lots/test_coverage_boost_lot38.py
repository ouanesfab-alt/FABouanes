"""
test_coverage_boost_lot38.py
Targets:
  - query.py: query_sa with SQLAlchemy select query (lines 80-84), explain_query_plan (line 76)
  - models_pkg/sales.py: _coerce_sale_type validator with SaleType enum vs string (lines 60, 94-96, 121-123)
  - sales/commands.py: recalc_sale_document_totals & delete edge cases
  - config.py: database_url validation & secret_key non-test mode (lines 102, 118, 123-126)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. query.py — query_sa & explain_query_plan
# ============================================================

def test_query_sa_compilation():
    """Lines 80-84: query_sa compiles SQLAlchemy Select query to SQL and executes via query_db."""
    from app.core.db_helpers.query import query_sa
    from sqlmodel import select
    from app.core.models import Client

    stmt = select(Client).where(Client.id == 1)

    with patch("app.core.db_helpers.query.query_db", return_value=[{"id": 1, "name": "Client A"}]) as mock_q:
        res = query_sa(stmt, one=True)

    assert res == [{"id": 1, "name": "Client A"}]
    mock_q.assert_called_once()


def test_explain_query_plan():
    """Line 76: explain_query_plan calls db_manager.explain_query_plan."""
    from app.core.db_helpers.query import explain_query_plan

    with patch("app.core.db_helpers.query.db_manager.explain_query_plan", return_value=[{"QUERY PLAN": "Seq Scan"}]):
        res = explain_query_plan("SELECT * FROM clients")

    assert len(res) == 1


# ============================================================
# 2. models_pkg/sales.py — _coerce_sale_type validator
# ============================================================

def test_models_sales_coerce_sale_type():
    """Lines 60, 94-96, 121-123: _coerce_sale_type with SaleType enum and string."""
    from app.core.models_pkg.sales import Sale, RawSale, SaleDocument, SaleType

    # String input
    s1 = Sale._coerce_sale_type("cash")
    assert s1 == SaleType.CASH

    # Enum input
    s2 = Sale._coerce_sale_type(SaleType.CREDIT)
    assert s2 == SaleType.CREDIT

    # RawSale validator
    rs1 = RawSale._coerce_sale_type("credit")
    assert rs1 == SaleType.CREDIT
    rs2 = RawSale._coerce_sale_type(SaleType.CASH)
    assert rs2 == SaleType.CASH

    # SaleDocument validator
    sd1 = SaleDocument._coerce_sale_type("cash")
    assert sd1 == SaleType.CASH
    sd2 = SaleDocument._coerce_sale_type(SaleType.CREDIT)
    assert sd2 == SaleType.CREDIT


# ============================================================
# 3. sales/commands.py — recalc_sale_document_totals
# ============================================================

@pytest.mark.asyncio
async def test_sales_commands_recalc_sale_document_totals():
    """Lines 229, 375, 429: recalc_sale_document_totals."""
    from app.modules.sales.commands import SalesCommands

    mock_session = AsyncMock()
    mock_doc = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_doc)

    mock_exec = MagicMock(scalar=MagicMock(return_value=300.0))
    mock_session.execute = AsyncMock(return_value=mock_exec)

    commands = SalesCommands(mock_session)
    commands._sum_document_lines = AsyncMock(side_effect=[
        {"total_amount": 1500.0, "paid_amount": 200.0, "due_amount": 1300.0, "line_count": 2},
        {"total_amount": 500.0, "paid_amount": 100.0, "due_amount": 400.0, "line_count": 1},
    ])

    await commands.recalc_sale_document_totals(document_id=1)

    assert mock_doc.total == 2000.0
    assert mock_doc.amount_paid == 300.0
    assert mock_doc.balance_due == 1700.0


# ============================================================
# 4. config.py — database_url validation
# ============================================================

def test_config_database_url_validation():
    """Lines 123-126: database_url validation for missing and invalid protocol."""
    from app.core.config import Settings

    with patch.dict("os.environ", {"DATABASE_URL": ""}):
        s = Settings(secret_key="test-key-32-bytes-minimum-length!", env="testing")
        with pytest.raises(RuntimeError) as exc_info:
            _ = s.database_url
        assert "doit etre specifie" in str(exc_info.value)

    with patch.dict("os.environ", {"DATABASE_URL": "mysql://user:pass@localhost/db"}):
        s2 = Settings(secret_key="test-key-32-bytes-minimum-length!", env="testing")
        with pytest.raises(RuntimeError) as exc_info2:
            _ = s2.database_url
        assert "Seul PostgreSQL" in str(exc_info2.value)
