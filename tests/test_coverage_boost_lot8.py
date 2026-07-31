"""Tests de couverture ciblés — Lot 8.

Couvre: db_helpers/manager.py (CompatRow, _wrap_rows, CompatCursor, _clean_params),
        sales/commands.py & sales/validation.py
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ── db_helpers/manager.py (72% → target ~85%) ──────────────────────


def test_compat_row_dict_and_index_access():
    """CompatRow supports both dict key and integer index access."""
    from app.core.db_helpers.manager import CompatRow

    row = CompatRow({"id": 1, "name": "Alice", "balance": Decimal("100.50")})
    assert row["id"] == 1
    assert row["name"] == "Alice"
    assert row[0] == 1
    assert row[1] == "Alice"
    assert row[2] == Decimal("100.50")


def test_wrap_rows_empty_description():
    """_wrap_rows returns original rows if description is None or empty."""
    from app.core.db_helpers.manager import _wrap_rows
    rows = [(1, "Alice")]
    assert _wrap_rows(rows, None) == rows
    assert _wrap_rows(rows, []) == rows


def test_wrap_rows_with_description():
    """_wrap_rows converts tuple rows into CompatRow objects using description column names."""
    from app.core.db_helpers.manager import _wrap_rows, CompatRow

    description = [("id", 1), ("name", 2)]
    rows = [(1, "Bob"), (2, "Charlie")]

    wrapped = _wrap_rows(rows, description)
    assert len(wrapped) == 2
    assert isinstance(wrapped[0], CompatRow)
    assert wrapped[0]["id"] == 1
    assert wrapped[0]["name"] == "Bob"
    assert wrapped[1][1] == "Charlie"


def test_compat_cursor_lifecycle():
    """CompatCursor fetchall, fetchone, close, and context manager work as expected."""
    from app.core.db_helpers.manager import CompatCursor, CompatRow

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [(10, "Item A")]
    mock_cur.fetchone.return_value = (10, "Item A")
    mock_cur.description = [("id", 1), ("item_name", 2)]
    mock_cur.lastrowid = 100

    cursor = CompatCursor(mock_cur)

    assert cursor.lastrowid == 100

    row = cursor.fetchone()
    assert isinstance(row, CompatRow)
    assert row["id"] == 10

    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["item_name"] == "Item A"

    with CompatCursor(mock_cur) as c:
        assert c is not None
    assert mock_cur.close.called


def test_compat_cursor_fetchone_none():
    """CompatCursor fetchone returns None when no row is found."""
    from app.core.db_helpers.manager import CompatCursor

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = None
    mock_cur.description = [("id", 1)]

    cursor = CompatCursor(mock_cur)
    assert cursor.fetchone() is None


def test_clean_params():
    """_clean_params converts float values inside tuples, lists, and dicts to Decimal."""
    from app.core.db_helpers.manager import _clean_params

    assert _clean_params(None) is None
    assert _clean_params("str") == "str"

    # Tuple of floats
    res_tuple = _clean_params((10.5, "hello", 42))
    assert isinstance(res_tuple[0], Decimal)
    assert res_tuple[0] == Decimal("10.5")

    # List of floats
    res_list = _clean_params([1.5, [2.5, "nested"]])
    assert isinstance(res_list[0], Decimal)
    assert isinstance(res_list[1][0], Decimal)

    # Dict of floats
    res_dict = _clean_params({"amount": 99.99, "name": "Test"})
    assert isinstance(res_dict["amount"], Decimal)


# ── sales/validation.py (96% → target 100%) ────────────────────────


def test_sales_validator_type_cash_no_client():
    """Cash sales without client are valid."""
    from app.modules.sales.validation import SalesValidator
    SalesValidator.validate_sale_type(None, "cash")  # Should not raise


def test_sales_validator_type_credit_no_client():
    """Credit sales without client raise ValidationError."""
    from app.modules.sales.validation import SalesValidator
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        SalesValidator.validate_sale_type(None, "credit")
    assert "client" in str(exc_info.value).lower()


def test_sales_validator_invalid_quantity():
    """Quantity <= 0 raises ValidationError."""
    from app.modules.sales.validation import SalesValidator
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        SalesValidator.validate_quantity(0)
    with pytest.raises(ValidationError):
        SalesValidator.validate_quantity(-5.0)
    SalesValidator.validate_quantity(1.5)  # Valid
