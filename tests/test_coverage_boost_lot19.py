"""Tests de couverture ciblés — Lot 19.

Couvre: modules/sales/validation.py (validate_stock_availability raw material missing & raw material stock insufficient)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.sales.validation import SalesValidator


# ── sales/validation.py (96% → target 100%) ─────────────────────────


@pytest.mark.asyncio
async def test_validate_stock_availability_raw_material_not_found():
    """validate_stock_availability raises NotFoundError if raw material does not exist."""
    session = AsyncMock()

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    with pytest.raises(NotFoundError):
        await SalesValidator.validate_stock_availability("raw", 999, 10.0, "kg", "", session)


@pytest.mark.asyncio
async def test_validate_stock_availability_raw_material_insufficient_stock():
    """validate_stock_availability raises ValidationError if raw material stock is insufficient."""
    session = AsyncMock()

    raw_item = MagicMock()
    raw_item.name = "Farine"
    raw_item.stock_qty = 5.0

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = raw_item
    session.execute.return_value = mock_res

    with pytest.raises(ValidationError) as exc_info:
        await SalesValidator.validate_stock_availability("raw", 1, 20.0, "kg", "", session)

    assert "Stock matière insuffisant" in str(exc_info.value)
