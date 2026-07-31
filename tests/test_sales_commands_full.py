"""Tests unitaires pour app/modules/sales/commands.py (Couverture > 90%)."""
from __future__ import annotations

from datetime import date
from unittest import mock
import pytest

from app.modules.sales.commands import SalesCommands
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema



@pytest.mark.asyncio
async def test_sales_commands_create_sale_from_form_single_line():
    mock_session = mock.AsyncMock()
    cmd = SalesCommands(mock_session)

    schema = SaleFormSchema(
        client_id=1,
        sale_date=date.today(),
        notes="Test vente form",
        lines=[
            SaleLineSchema(item_key="finished:10", quantity=2.0, unit="kg", unit_price=150.0, custom_item_name="")

        ]
    )

    with mock.patch("app.modules.sales.validation.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "create_sale_record", return_value=("finished", 55)), \
         mock.patch.object(cmd.sale_repo, "get_sale_detail", return_value={"id": 55, "row_kind": "finished"}):

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "line"
        assert res["first_line_id"] == 55
        assert res["print_doc_type"] == "sale_finished"


@pytest.mark.asyncio
async def test_sales_commands_create_sale_from_form_multi_line():
    mock_session = mock.AsyncMock()
    cmd = SalesCommands(mock_session)

    schema = SaleFormSchema(
        client_id=1,
        sale_date=date.today(),
        notes="Test multi-line",
        lines=[
            SaleLineSchema(item_key="finished:10", quantity=2.0, unit="kg", unit_price=150.0),
            SaleLineSchema(item_key="raw:5", quantity=1.0, unit="kg", unit_price=80.0)

        ]
    )

    with mock.patch("app.modules.sales.validation.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "_insert_sale_document", return_value=100), \
         mock.patch.object(cmd, "create_sale_record", side_effect=[("finished", 55), ("raw", 12)]), \
         mock.patch.object(cmd.doc_repo, "get_by_id", return_value=mock.MagicMock(model_dump=lambda: {})):

        res = await cmd.create_sale_from_form(schema)
        assert res["mode"] == "document"
        assert res["document_id"] == 100
        assert res["line_count"] == 2


@pytest.mark.asyncio
async def test_sales_commands_edit_single_sale_from_form():
    mock_session = mock.AsyncMock()
    cmd = SalesCommands(mock_session)

    schema = SaleFormSchema(
        client_id=1,
        sale_date=date.today(),
        notes="Edit note",
        lines=[
            SaleLineSchema(item_key="finished:10", quantity=3.0, unit="kg", unit_price=150.0)

        ]
    )

    with mock.patch.object(cmd.sale_repo, "get_sale_detail", side_effect=[{"id": 55, "document_id": None}, {"id": 60}]), \
         mock.patch("app.modules.sales.validation.SalesValidator.validate_client", return_value=None), \
         mock.patch.object(cmd, "reverse_sale", return_value=True), \
         mock.patch.object(cmd, "create_sale_record", return_value=("finished", 60)):

        res = await cmd.edit_single_sale_from_form("finished", 55, schema)
        assert res["mode"] == "line"
        assert res["first_line_id"] == 60


@pytest.mark.asyncio
async def test_sales_commands_delete_sale_by_id():
    mock_session = mock.AsyncMock()
    cmd = SalesCommands(mock_session)

    with mock.patch.object(cmd.sale_repo, "get_sale_detail", return_value={"id": 55}), \
         mock.patch.object(cmd, "reverse_sale", return_value=True):

        ok = await cmd.delete_sale_by_id("finished", 55)
        assert ok is True
