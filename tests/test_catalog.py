"""
Tests unitaires complets pour le module Catalogue & Stocks (app/modules/catalog).
Conforme à la Règle 4 de GEMINI.md.
"""

from __future__ import annotations

from decimal import Decimal


from app.modules.catalog.schemas import (
    FinishedProductCreateSchema,
    RawMaterialCreateSchema,
    parse_decimal,
)
from app.modules.catalog.stock_service import (
    qty_to_kg,
    unit_choices,
    unit_price_to_kg,
)


# ── Schemas Tests ─────────────────────────────────────────────────────────────


def test_parse_decimal_various_inputs():
    assert parse_decimal("123.45") == Decimal("123.45")
    assert parse_decimal("1 234,56") == Decimal("1234.56")
    assert parse_decimal(100) == Decimal("100")
    assert parse_decimal(None) == Decimal("0.00")
    assert parse_decimal("") == Decimal("0.00")


def test_raw_material_create_schema_coercion():
    schema = RawMaterialCreateSchema(
        name="Farine T55",
        unit="kg",
        stock_qty="500.5",
        avg_cost="45.20",
        sale_price="60.00",
        alert_threshold="50.0",
    )
    assert schema.name == "Farine T55"
    assert schema.stock_qty == Decimal("500.5")
    assert schema.avg_cost == Decimal("45.20")
    assert schema.sale_price == Decimal("60.00")


def test_finished_product_create_schema_coercion():
    schema = FinishedProductCreateSchema(
        name="Couscous Moyen",
        default_unit="sac (50kg)",
        stock_qty=10,
        sale_price=5500,
        avg_cost=4200,
    )
    assert schema.name == "Couscous Moyen"
    assert schema.stock_qty == Decimal("10")
    assert schema.sale_price == Decimal("5500")


# ── Conversions & Calculations Tests ──────────────────────────────────────────


def test_qty_to_kg_units():
    # Bag 50kg
    assert qty_to_kg(Decimal("2"), "sac (50kg)") == Decimal("100")
    # Bag 25kg
    assert qty_to_kg(Decimal("4"), "sac (25kg)") == Decimal("100")
    # Quintal (100kg)
    assert qty_to_kg(Decimal("1.5"), "Qt") == Decimal("150")
    # Tonne (1000kg)
    assert qty_to_kg(Decimal("0.5"), "tonne") == Decimal("500")
    # Standard kg
    assert qty_to_kg(Decimal("42.5"), "kg") == Decimal("42.5")


def test_unit_price_to_kg_units():
    # 5000 DZD per 50kg bag -> 100 DZD/kg
    assert unit_price_to_kg(Decimal("5000"), "sac (50kg)") == Decimal("100")
    # 10000 DZD per quintal -> 100 DZD/kg
    assert unit_price_to_kg(Decimal("10000"), "Qt") == Decimal("100")
    # 80000 DZD per tonne -> 80 DZD/kg
    assert unit_price_to_kg(Decimal("80000"), "tonne") == Decimal("80")
    # Standard kg
    assert unit_price_to_kg(Decimal("120"), "kg") == Decimal("120")


def test_unit_choices():
    choices = unit_choices()
    assert "kg" in choices
    assert "sac (50kg)" in choices
    assert "Qt" in choices
    assert "tonne" in choices
