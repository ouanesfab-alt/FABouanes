from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.sales.commands import SalesCommands
from app.services.stock_service import qty_to_kg, unit_price_to_kg


def test_qty_and_price_conversions():
    assert qty_to_kg(2, "sac (50kg)") == 100.0
    assert qty_to_kg(1.5, "Qt") == 150.0
    assert unit_price_to_kg(5000, "sac (50kg)") == 100.0


@pytest.mark.asyncio
async def test_sales_commands_rounding_precision():
    session = MagicMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()

    # Mock product query
    mock_product = MagicMock()
    mock_product.stock_qty = 100.0
    mock_product.avg_cost = 33.33333333
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_product
    session.execute.return_value = mock_res

    commands = SalesCommands(session)
    commands.recalc_sale_document_totals = AsyncMock()
    commands.record_stock_movement = AsyncMock()

    # 1.333333 quantity @ 10.5555 unit price -> total should be rounded to 2 decimals
    kind, row_id = await commands.create_sale_record(
        client_id=1,
        item_kind="finished",
        item_id=10,
        qty=1.333333,
        unit="kg",
        unit_price=10.5555,
        sale_type="credit",
        sale_date="2026-08-03",
        notes="",
        amount_paid_input=5.1234
    )

    added_sale = None
    for call in session.add.call_args_list:
        obj = call[0][0]
        if hasattr(obj, "total"):
            added_sale = obj
            break

    assert added_sale is not None
    # total = 1.333333 * 10.5555 = 14.07399... -> 14.07
    assert added_sale.total == 14.07
    # amount_paid = round(5.1234, 2) = 5.12
    assert added_sale.amount_paid == 5.12
    # balance_due = 14.07 - 5.12 = 8.95
    assert added_sale.balance_due == 8.95
