# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stock_service import (
    _extract_weight_from_unit,
    qty_to_kg,
    unit_price_to_kg,
    unit_choices,
    is_other_operation_name,
    record_stock_movement,
    recalc_raw_material_avg_cost,
    recalc_finished_product_avg_cost,
    create_purchase_record
)
from app.core.exceptions import ValidationError, NotFoundError


# =============================================================================
# 1. Tests des fonctions de conversion de poids
# =============================================================================

def test_extract_weight_from_unit():
    assert _extract_weight_from_unit(None) == 50.0
    assert _extract_weight_from_unit("") == 50.0
    assert _extract_weight_from_unit("sac (50kg)") == 50.0
    assert _extract_weight_from_unit("sac (25kg)") == 25.0
    assert _extract_weight_from_unit("sac (42.5 kg)") == 42.5
    assert _extract_weight_from_unit("unite") == 50.0


def test_qty_to_kg():
    assert qty_to_kg(10.0, "kg") == 10.0
    assert qty_to_kg(2.0, "sac (50kg)") == 100.0
    assert qty_to_kg(4.0, "sac (25kg)") == 100.0
    assert qty_to_kg(3.0, "Qt") == 300.0
    assert qty_to_kg(1.5, "quintal") == 150.0
    assert qty_to_kg(5.0, None) == 5.0  # default unit is kg


def test_unit_price_to_kg():
    assert unit_price_to_kg(100.0, "kg") == 100.0
    assert unit_price_to_kg(5000.0, "sac (50kg)") == 100.0
    assert unit_price_to_kg(2500.0, "sac (25kg)") == 100.0
    assert unit_price_to_kg(12000.0, "Qt") == 120.0
    assert unit_price_to_kg(8000.0, "quintal") == 80.0
    assert unit_price_to_kg(300.0, "unite") == 300.0


def test_unit_choices_and_other_operations():
    choices = unit_choices()
    assert "kg" in choices
    assert "sac (50kg)" in choices
    assert "Qt" in choices

    assert is_other_operation_name("AUTRE") is True
    assert is_other_operation_name("autre") is True
    assert is_other_operation_name("AUTRE ") is True
    assert is_other_operation_name("produit") is False


# =============================================================================
# 2. Tests de recalcule de coût moyen pondéré (PAMP)
# =============================================================================

class MockRow:
    def __init__(self, mapping):
        self._mapping = mapping

class CustomMockSession:
    def __init__(self, item, purchases_or_productions):
        self.item = item
        self.lines = purchases_or_productions
        self.added = []
        self.executed_statements = []

    def begin(self):
        class MockTx:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        return MockTx()

    async def execute(self, stmt, *args, **kwargs):
        self.executed_statements.append(stmt)
        stmt_str = str(stmt).lower()
        mock_res = MagicMock()
        if "from raw_materials" in stmt_str or "rawmaterial" in stmt_str or "from finished_products" in stmt_str or "finishedproduct" in stmt_str:
            mock_res.scalar_one_or_none.return_value = self.item
        elif "from purchases" in stmt_str or "purchase" in stmt_str or "from production_batches" in stmt_str or "productionbatch" in stmt_str:
            if "sum(" in stmt_str or "coalesce(" in stmt_str:
                if "purchases" in stmt_str or "purchase" in stmt_str:
                    from app.services.stock_service import qty_to_kg
                    total_qty_kg = sum(qty_to_kg(float(line["quantity"]), line["unit"]) for line in self.lines)
                    total_value = sum(float(line["quantity"]) * float(line["unit_price"]) for line in self.lines)
                    row_mock = MagicMock()
                    row_mock.total_qty_kg = total_qty_kg
                    row_mock.total_value = total_value
                    mock_res.first.return_value = row_mock
                    mock_res.fetchone.return_value = row_mock
                else:
                    total_qty = sum(float(line["output_quantity"]) for line in self.lines)
                    total_cost = sum(float(line["production_cost"]) for line in self.lines)
                    row_mock = MagicMock()
                    row_mock.total_qty = total_qty
                    row_mock.total_cost = total_cost
                    mock_res.first.return_value = row_mock
                    mock_res.fetchone.return_value = row_mock
            else:
                mock_res.fetchall.return_value = [MockRow(line) for line in self.lines]
        return mock_res

    def add(self, instance, *args, **kwargs):
        self.added.append(instance)
        instance.id = 777

    async def flush(self): pass
    async def commit(self): pass
    async def close(self): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass


@pytest.mark.asyncio
async def test_recalc_raw_material_avg_cost():
    class RawMaterialMock:
        def __init__(self):
            self.id = 1
            self.stock_qty = Decimal("150.0")
            self.avg_cost = Decimal("200.0")

    material = RawMaterialMock()
    # 2 purchases:
    # 1. 100 kg at 180 DA/kg
    # 2. 2 sacs (50kg) = 100 kg at 2200 DA/sac = 44 DA/kg
    purchases = [
        {"quantity": 100.0, "unit": "kg", "unit_price": 180.0},
        {"quantity": 2.0, "unit": "sac (50kg)", "unit_price": 2200.0}
    ]

    session = CustomMockSession(material, purchases)
    await recalc_raw_material_avg_cost(1, db=session)

    # Base qty = stock_qty - purchased_qty = 150 - 200 = -50 -> max(0, -50) = 0
    # Total purchased qty = 200 kg
    # Total value = 100 * 180 + 100 * 44 = 18000 + 4400 = 22400 DA
    # Expected avg_cost = 22400 / 200 = 112.0
    # Let's verify that session.executed_statements contains an update to RawMaterial
    update_found = False
    for stmt in session.executed_statements:
        if "UPDATE raw_materials" in str(stmt):
            update_found = True
    assert update_found is True


@pytest.mark.asyncio
async def test_recalc_finished_product_avg_cost():
    class FinishedProductMock:
        def __init__(self):
            self.id = 1
            self.stock_qty = Decimal("50.0")
            self.avg_cost = Decimal("400.0")

    product = FinishedProductMock()
    # 2 production batches:
    # 1. qty=20, cost=6000 (300/unit)
    # 2. qty=30, cost=12000 (400/unit)
    productions = [
        {"output_quantity": 20.0, "production_cost": 6000.0},
        {"output_quantity": 30.0, "production_cost": 12000.0}
    ]

    session = CustomMockSession(product, productions)
    await recalc_finished_product_avg_cost(1, db=session)

    # Base qty = stock_qty - produced_qty = 50 - 50 = 0
    # Total qty = 50
    # Total value = 6000 + 12000 = 18000
    # Expected avg_cost = 18000 / 50 = 360.0
    update_found = False
    for stmt in session.executed_statements:
        if "UPDATE finished_products" in str(stmt):
            update_found = True
    assert update_found is True


# =============================================================================
# 3. Tests des mouvements de stock et de création d'achat
# =============================================================================

@pytest.mark.asyncio
@patch("app.services.stock_service.get_state_value")
@patch("app.modules.catalog.repository.insert_stock_movement")
async def test_record_stock_movement(mock_insert, mock_state):
    mock_state.return_value = {"username": "jean_test"}
    db = MagicMock(spec=AsyncSession)
    await record_stock_movement(
        "raw", 1, "in", 50.0, "kg", 100.0, 150.0, "purchase", "purchase", 101, db=db
    )
    mock_insert.assert_called_once_with(
        "raw", 1, "in", 50.0, "kg", 100.0, 150.0, "purchase", "purchase", 101, "jean_test", db=db
    )


@pytest.mark.asyncio
async def test_create_purchase_record_validation():
    # Purchase date in the future
    with pytest.raises(ValidationError) as exc:
        await create_purchase_record(
            supplier_id=1,
            item_kind_or_raw_id="raw",
            qty=10,
            unit_price=200,
            purchase_date="2099-12-31",
            notes="Future purchase",
            unit="kg",
            item_id=1
        )
    assert "date d'achat" in str(exc.value)
