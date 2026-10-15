"""
Tests unitaires complets pour le module Ventes (app/modules/sales).
Conforme à la Règle 4 de GEMINI.md.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.core.models import FinishedProduct
from app.modules.sales.commands import SalesCommands
from app.modules.sales.queries import SalesQueries
from app.modules.sales.schemas import (
    SaleFormSchema,
    SaleLineSchema,
    SalesValidator,
)


# ── Schemas & Validators Tests ────────────────────────────────────────────────


def test_sales_validator_cash_without_client():
    SalesValidator.validate_sale_type(None, "cash")


def test_sales_validator_credit_with_client():
    SalesValidator.validate_sale_type(42, "credit")


def test_sales_validator_credit_without_client_raises():
    with pytest.raises(ValidationError):
        SalesValidator.validate_sale_type(None, "credit")


def test_sales_validator_quantity_positive():
    SalesValidator.validate_quantity(Decimal("10.00"))


def test_sales_validator_quantity_negative_raises():
    with pytest.raises(ValidationError):
        SalesValidator.validate_quantity(Decimal("-1.00"))


def test_sale_line_schema_decimal():
    line = SaleLineSchema(
        item_key="finished:12",
        quantity="25.5",
        unit="kg",
        unit_price="180.00",
        custom_item_name="",
    )
    assert isinstance(line.quantity, Decimal)
    assert line.quantity == Decimal("25.5")
    assert isinstance(line.unit_price, Decimal)
    assert line.unit_price == Decimal("180.00")


def test_sale_form_schema_multi_line_dict():
    form_data = {
        "client_id": 1,
        "sale_type": "credit",
        "sale_date": date.today().isoformat(),
        "lines": [
            {"item_key": "finished:1", "quantity": "5", "unit_price": "200"},
            {"item_key": "raw:2", "quantity": "10", "unit_price": "80"},
        ],
    }
    schema = SaleFormSchema.model_validate(form_data)
    assert schema.client_id == 1
    assert len(schema.lines) == 2
    assert schema.lines[0].quantity == Decimal("5")
    assert schema.lines[1].quantity == Decimal("10")


# ── Commands Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sales_commands_create_finished_sale():
    session = mock.AsyncMock()
    cmd = SalesCommands(session)

    product = FinishedProduct(
        id=10,
        name="Couscous Fin",
        stock_qty=Decimal("100.00"),
        avg_cost=Decimal("75.00"),
        sale_price=Decimal("120.00"),
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = product
    session.execute.return_value = mock_res

    with mock.patch("app.modules.sales.schemas.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "record_stock_movement", return_value=None), \
         mock.patch.object(cmd, "recalc_sale_document_totals", return_value=None):

        kind, row_id = await cmd.create_sale_record(
            client_id=1,
            item_kind="finished",
            item_id=10,
            qty=Decimal("10.00"),
            unit="kg",
            unit_price=Decimal("120.00"),
            sale_type="cash",
            sale_date=date.today(),
            notes="Vente comptoir",
            amount_paid_input=Decimal("1200.00"),
        )

        assert kind == "finished"
        assert session.add.called
        assert product.stock_qty == Decimal("90.00")


@pytest.mark.asyncio
async def test_sales_commands_create_sale_from_form_single_line():
    session = mock.AsyncMock()
    cmd = SalesCommands(session)

    schema = SaleFormSchema(
        client_id=1,
        sale_date=date.today(),
        notes="Test vente mono",
        lines=[
            SaleLineSchema(item_key="finished:10", quantity=Decimal("2.0"), unit="kg", unit_price=Decimal("150.0")),
        ],
    )

    with mock.patch("app.modules.sales.schemas.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "create_sale_record", return_value=("finished", 55)), \
         mock.patch.object(cmd.sale_repo, "get_sale_detail", return_value={"id": 55, "row_kind": "finished"}):

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "line"
        assert res["first_line_id"] == 55
        assert res["print_doc_type"] == "sale_finished"


@pytest.mark.asyncio
async def test_sales_commands_create_sale_from_form_multi_line():
    session = mock.AsyncMock()
    cmd = SalesCommands(session)

    schema = SaleFormSchema(
        client_id=1,
        sale_date=date.today(),
        notes="Test vente multi",
        lines=[
            SaleLineSchema(item_key="finished:10", quantity=Decimal("2.0"), unit="kg", unit_price=Decimal("150.0")),
            SaleLineSchema(item_key="raw:5", quantity=Decimal("1.0"), unit="kg", unit_price=Decimal("80.0")),
        ],
    )

    with mock.patch("app.modules.sales.schemas.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "_insert_sale_document", return_value=100), \
         mock.patch.object(cmd, "create_sale_record", side_effect=[("finished", 55), ("raw", 12)]), \
         mock.patch.object(cmd.doc_repo, "get_by_id", return_value=mock.MagicMock(model_dump=lambda: {})):

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "document"
        assert res["document_id"] == 100
        assert res["line_count"] == 2


# ── Queries Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sales_queries():
    session = mock.AsyncMock()
    queries = SalesQueries(session)

    with mock.patch.object(queries.sale_repo, "list_sales_paginated", return_value=([], 0)):
        res, cnt = await queries.list_sales(search="test")
        assert res == []
        assert cnt == 0

    with mock.patch.object(queries.sale_repo, "list_sellable_items", return_value=[]):
        ctx = await queries.sale_form_context()
        assert "sellable_items" in ctx
        assert "units" in ctx
