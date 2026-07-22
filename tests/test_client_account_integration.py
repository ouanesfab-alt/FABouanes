# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.client_account_service import (
    client_balance,
    get_open_credit_entries,
    apply_payment_to_entry,
    reverse_payment_allocations,
    create_payment_record
)


# =============================================================================
# Mock classes for database rows
# =============================================================================

class MockRow:
    def __init__(self, mapping):
        self._mapping = mapping
        # Add support for indexing like row[0]
        self.mapping_values = list(mapping.values())

    def __getitem__(self, idx):
        return self.mapping_values[idx]

    def first(self):
        return self


class CustomAccountMockSession:
    def __init__(self, balance_val=15000.0, open_entries=None, sale_obj=None, client_exists=True):
        self.balance_val = balance_val
        self.open_entries = open_entries or []
        self.sale_obj = sale_obj
        self.client_exists = client_exists
        self.executed_statements = []
        self.added = []

    def begin(self):
        class MockTx:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        return MockTx()

    async def execute(self, stmt, *args, **kwargs):
        self.executed_statements.append(stmt)
        stmt_str = str(stmt).lower()
        mock_res = MagicMock()

        if "clients_with_stats" in stmt_str:
            mock_res.first.return_value = MockRow({"current_debt": self.balance_val})
            return mock_res
        elif "sales" in stmt_str or "raw_sales" in stmt_str:
            if "sum" in stmt_str or "union" in stmt_str:
                # Return open entries rows
                mock_res.fetchall.return_value = [MockRow(entry) for entry in self.open_entries]
                return mock_res
            else:
                # Return sale object scalar
                mock_res.scalars.return_value.first.return_value = self.sale_obj
                return mock_res
        elif "clients" in stmt_str:
            # Client check
            mock_res.first.return_value = MockRow({"id": 1}) if self.client_exists else None
            return mock_res

        return mock_res

    def add(self, instance, *args, **kwargs):
        self.added.append(instance)
        instance.id = 999

    async def flush(self): pass
    async def commit(self): pass
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass


# =============================================================================
# Tests
# =============================================================================

@pytest.mark.asyncio
async def test_client_balance():
    session = CustomAccountMockSession(balance_val=25000.0)
    bal = await client_balance(1, db=session)
    assert bal == 25000.0


@pytest.mark.asyncio
async def test_get_open_credit_entries():
    entries = [
        {"item_kind": "finished", "id": 101, "client_id": 1, "client_name": "Lamine", "item_name": "Produit A", "balance_due": 5000.0, "sale_date": "2026-07-01", "total": 10000.0, "document_id": 10},
        {"item_kind": "raw", "id": 102, "client_id": 1, "client_name": "Lamine", "item_name": "Ciment", "balance_due": 3000.0, "sale_date": "2026-07-02", "total": 6000.0, "document_id": 11}
    ]
    session = CustomAccountMockSession(open_entries=entries)
    res = await get_open_credit_entries(1, db=session)
    assert len(res) == 2
    assert res[0]["item_kind"] == "finished"
    assert res[1]["item_name"] == "Ciment"


@pytest.mark.asyncio
@patch("app.services.stock_service.recalc_sale_document_totals", new_callable=AsyncMock)
async def test_apply_payment_to_entry(mock_recalc):
    # Apply to finished sale
    session = CustomAccountMockSession()
    # Mocking sale object
    class SaleMock:
        def __init__(self):
            self.id = 101
            self.balance_due = 5000.0
            self.amount_paid = 5000.0
            self.document_id = 10

    session.sale_obj = SaleMock()

    paid = await apply_payment_to_entry("finished", 101, 3000.0, db=session)
    assert paid == 3000.0


@pytest.mark.asyncio
@patch("app.services.stock_service.recalc_sale_document_totals", new_callable=AsyncMock)
async def test_reverse_payment_allocations(mock_recalc):
    # Mocking payment row with metadata allocation
    allocation_meta = json.dumps([
        {"kind": "finished", "id": 101, "amount": 2000.0},
        {"kind": "raw", "id": 102, "amount": 1000.0}
    ])
    payment_row = {
        "payment_type": "versement",
        "allocation_meta": allocation_meta,
        "keys": lambda: ["payment_type", "allocation_meta"]
    }

    class SaleMock:
        def __init__(self):
            self.id = 101
            self.document_id = 10

    session = CustomAccountMockSession(sale_obj=SaleMock())
    await reverse_payment_allocations(payment_row, db=session)
    # Ensure update statements were executed
    assert len(session.executed_statements) > 0


from app.core.exceptions import NotFoundError, ValidationError

@pytest.mark.asyncio
async def test_create_payment_record_validation():
    session = CustomAccountMockSession(client_exists=False)
    with pytest.raises((ValueError, NotFoundError)) as exc:
        await create_payment_record(
            client_id=999,
            amount=5000,
            payment_date="2026-07-01",
            notes="Invalid client",
            payment_type="versement",
            db=session
        )
    assert "Client introuvable" in str(exc.value)


@pytest.mark.asyncio
async def test_create_payment_record_avance():
    session = CustomAccountMockSession(client_exists=True)
    pay_id = await create_payment_record(
        client_id=1,
        amount=10000,
        payment_date="2026-07-01",
        notes="Avance client",
        payment_type="avance",
        db=session
    )
    assert pay_id == 999
    assert len(session.added) == 1
    assert session.added[0].payment_type == "avance"
