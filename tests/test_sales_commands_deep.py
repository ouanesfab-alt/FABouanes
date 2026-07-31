"""Tests unitaires approfondis pour app/modules/sales/commands.py et queries.py (Vague 2 — couverture > 90%)."""
from __future__ import annotations

from datetime import date
from unittest import mock
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.modules.sales.commands import SalesCommands
from app.modules.sales.queries import SalesQueries
from app.core.models import FinishedProduct, RawMaterial, Sale


@pytest.mark.asyncio
async def test_sales_queries_contexts():
    mock_session = AsyncMock()
    queries = SalesQueries(mock_session)

    # list_sales
    mock_session.execute.return_value.scalars.return_value.all.return_value = []
    with mock.patch.object(queries.sale_repo, "list_sales_paginated", return_value=([], 0)):
        res, cnt = await queries.list_sales(search="test")
        assert res == []
        assert cnt == 0

    # sale_form_context
    with mock.patch.object(queries.sale_repo, "list_sellable_items", return_value=[]):
        ctx = await queries.sale_form_context()
        assert "sellable_items" in ctx
        assert "units" in ctx

    # get_sale_document_context non-existent
    with mock.patch.object(queries.doc_repo, "get_by_id", return_value=None):
        doc_ctx = await queries.get_sale_document_context(999)
        assert doc_ctx is None

    # get_sale_edit_context with document_id redirect
    mock_sale = {"id": 1, "row_kind": "finished", "document_id": 50, "client_id": 2}
    with mock.patch.object(queries.sale_repo, "get_sale_detail", return_value=mock_sale), \
         mock.patch.object(queries, "get_sale_document_context", return_value={"sale_document": {"id": 50}}):
        edit_ctx = await queries.get_sale_edit_context("finished", 1)
        assert edit_ctx["redirect_document_id"] == 50


@pytest.mark.asyncio
async def test_sales_commands_create_raw_sale():
    mock_session = AsyncMock()
    cmd = SalesCommands(mock_session)

    raw_mat = RawMaterial(id=5, name="Sucre", stock_qty=100.0, avg_cost=50.0)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = raw_mat
    mock_session.execute.return_value = mock_res

    with mock.patch("app.modules.sales.validation.SalesValidator.validate_client", return_value=None), \
         mock.patch("app.modules.sales.validation.SalesValidator.validate_stock_availability", return_value=(raw_mat, 10.0)), \
         mock.patch.object(cmd, "record_stock_movement", return_value=None), \
         mock.patch.object(cmd, "recalc_sale_document_totals", return_value=None):

        kind, row_id = await cmd.create_sale_record(
            client_id=1,
            item_kind="raw",
            item_id=5,
            qty=10.0,
            unit="kg",
            unit_price=100.0,
            sale_type="credit",
            sale_date=date.today(),
            notes="Vente sucre",
            amount_paid_input=200.0,
        )

        assert kind == "raw"
        assert raw_mat.stock_qty == 90.0


@pytest.mark.asyncio
async def test_sales_commands_reverse_sale():
    mock_session = AsyncMock()
    cmd = SalesCommands(mock_session)

    sale_item = Sale(
        id=10,
        finished_product_id=3,
        quantity=5.0,
        unit="unite",
        total=500.0,
        document_id=20,
    )
    product = FinishedProduct(id=3, name="Produit A", stock_qty=50.0)

    mock_res_sale = MagicMock()
    mock_res_sale.scalar_one_or_none.return_value = sale_item

    mock_res_prod = MagicMock()
    mock_res_prod.scalar_one_or_none.return_value = product

    mock_session.execute.side_effect = [mock_res_sale, mock_res_prod, MagicMock()]

    with mock.patch.object(cmd, "record_stock_movement", return_value=None), \
         mock.patch.object(cmd, "recalc_sale_document_totals", return_value=None):

        deleted = await cmd.reverse_sale("finished", 10)
        assert deleted is True
        assert product.stock_qty == 55.0  # stock restored by +5.0


