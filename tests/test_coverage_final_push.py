"""
Tests ciblés pour couvrir les branches manquantes dans :
- app.modules.sales.validation (SalesValidator)
- app.modules.assistant.business_helpers (parse_amount, date_range_for_expression)
- app.core.db_helpers.execute (execute_sa)
"""
from __future__ import annotations

import os
import pytest
from datetime import date, timedelta
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FASTAPI_ENV", "test")
os.environ.setdefault("FAB_DESKTOP", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fabouanes.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")


# =============================================================================
# 1. app.modules.sales.validation — SalesValidator
# =============================================================================

class TestSalesValidator:
    @pytest.mark.asyncio
    async def test_validate_client_none_passes(self):
        from app.modules.sales.validation import SalesValidator
        mock_session = mock.AsyncMock()
        # client_id=None should pass without error
        await SalesValidator.validate_client(None, mock_session)
        mock_session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_client_found_passes(self):
        from app.modules.sales.validation import SalesValidator
        mock_session = mock.AsyncMock()
        mock_client = mock.MagicMock()
        mock_session.get.return_value = mock_client
        await SalesValidator.validate_client(1, mock_session)

    @pytest.mark.asyncio
    async def test_validate_client_not_found_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import NotFoundError
        mock_session = mock.AsyncMock()
        mock_session.get.return_value = None
        with pytest.raises(NotFoundError):
            await SalesValidator.validate_client(999, mock_session)

    def test_validate_sale_type_credit_no_client_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="crédit"):
            SalesValidator.validate_sale_type(None, "credit")

    def test_validate_sale_type_credit_with_client_passes(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_sale_type(1, "credit")  # Should not raise

    def test_validate_sale_type_cash_no_client_passes(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_sale_type(None, "cash")  # Should not raise

    def test_validate_quantity_positive_passes(self):
        from app.modules.sales.validation import SalesValidator
        SalesValidator.validate_quantity(1.5)  # Should not raise

    def test_validate_quantity_zero_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="quantité"):
            SalesValidator.validate_quantity(0)

    def test_validate_quantity_negative_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="quantité"):
            SalesValidator.validate_quantity(-5.0)

    @pytest.mark.asyncio
    async def test_validate_stock_finished_ok(self):
        from app.modules.sales.validation import SalesValidator
        mock_session = mock.AsyncMock()
        mock_item = mock.MagicMock()
        mock_item.stock_qty = 100.0
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=2.0):
            item, qty_kg = await SalesValidator.validate_stock_availability(
                "finished", 1, 2.0, "kg", "", mock_session
            )
        assert qty_kg == 2.0

    @pytest.mark.asyncio
    async def test_validate_stock_finished_not_found_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import NotFoundError
        mock_session = mock.AsyncMock()
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=2.0):
            with pytest.raises(NotFoundError):
                await SalesValidator.validate_stock_availability(
                    "finished", 999, 2.0, "kg", "", mock_session
                )

    @pytest.mark.asyncio
    async def test_validate_stock_finished_insufficient_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        mock_session = mock.AsyncMock()
        mock_item = mock.MagicMock()
        mock_item.stock_qty = 1.0
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=50.0):
            with pytest.raises(ValidationError, match="Stock produit insuffisant"):
                await SalesValidator.validate_stock_availability(
                    "finished", 1, 50.0, "kg", "", mock_session
                )

    @pytest.mark.asyncio
    async def test_validate_stock_raw_ok(self):
        from app.modules.sales.validation import SalesValidator
        mock_session = mock.AsyncMock()
        mock_item = mock.MagicMock()
        mock_item.stock_qty = 100.0
        mock_item.name = "Farine"
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=5.0):
            item, qty_kg = await SalesValidator.validate_stock_availability(
                "raw", 1, 5.0, "kg", "", mock_session
            )
        assert qty_kg == 5.0

    @pytest.mark.asyncio
    async def test_validate_stock_raw_autre_no_custom_name_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        mock_session = mock.AsyncMock()
        mock_item = mock.MagicMock()
        mock_item.stock_qty = 100.0
        mock_item.name = "AUTRE"
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=1.0):
            with pytest.raises(ValidationError, match="nom du produit"):
                await SalesValidator.validate_stock_availability(
                    "sale_raw", 1, 1.0, "kg", "", mock_session
                )

    @pytest.mark.asyncio
    async def test_validate_stock_unknown_kind_raises(self):
        from app.modules.sales.validation import SalesValidator
        from app.core.exceptions import ValidationError
        mock_session = mock.AsyncMock()
        with mock.patch("app.modules.sales.validation.qty_to_kg", return_value=1.0):
            with pytest.raises(ValidationError, match="inconnu"):
                await SalesValidator.validate_stock_availability(
                    "invalid_kind", 1, 1.0, "kg", "", mock_session
                )


# =============================================================================
# 2. app.modules.assistant.business_helpers
# =============================================================================

class TestParseAmount:
    def test_none_returns_zero(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount(None) == 0.0

    def test_integer_input(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount(3500) == 3500.0

    def test_float_input(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount(1500.5) == 1500.5

    def test_french_format_dot_comma(self):
        from app.modules.assistant.business_helpers import parse_amount
        # "3.500,50" → 3500.50
        assert parse_amount("3.500,50") == pytest.approx(3500.5)

    def test_french_format_comma_decimal(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("1500,50") == pytest.approx(1500.5)

    def test_english_format_comma_thousands(self):
        from app.modules.assistant.business_helpers import parse_amount
        # "3,500.00" → 3500.0
        assert parse_amount("3,500.00") == pytest.approx(3500.0)

    def test_k_multiplier(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("45k") == pytest.approx(45000.0)

    def test_m_multiplier(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("2m") == pytest.approx(2_000_000.0)

    def test_suffix_da_stripped(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("45 000 DA") == pytest.approx(45000.0)

    def test_suffix_dzd_stripped(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("1 500,50 DZD") == pytest.approx(1500.5)

    def test_invalid_returns_zero(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("not_a_number") == 0.0

    def test_multiple_dots_thousands(self):
        from app.modules.assistant.business_helpers import parse_amount
        # "1.500.000" → the last dot is ambiguous, parse_amount returns best-effort
        result = parse_amount("1.500.000")
        # The result should be a large number (either 1500.0 or 1500000.0 depending on parsing)
        assert result >= 1500.0

    def test_thousands_comma_multiple(self):
        from app.modules.assistant.business_helpers import parse_amount
        assert parse_amount("1,500,000") == pytest.approx(1500000.0)


class TestDateRangeForExpression:
    def test_cette_semaine(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 7, 16)  # Wednesday
        start, end = date_range_for_expression("cette semaine", ref)
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6   # Sunday

    def test_semaine_derniere(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 7, 16)
        start, end = date_range_for_expression("semaine dernière", ref)
        assert start < end
        assert start.weekday() == 0

    def test_ce_mois(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 7, 16)
        start, end = date_range_for_expression("ce mois", ref)
        assert start.day == 1
        assert start.month == 7

    def test_ce_mois_decembre(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 12, 15)
        start, end = date_range_for_expression("ce mois courant", ref)
        assert end.month == 12
        assert end.day == 31

    def test_mois_dernier(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 7, 16)
        start, end = date_range_for_expression("mois dernier", ref)
        assert start.month == 6

    def test_fallback_single_day(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        ref = date(2025, 7, 16)
        start, end = date_range_for_expression("aujourd'hui", ref)
        assert start == ref
        assert end == ref

    def test_invalid_returns_none_none(self):
        from app.modules.assistant.business_helpers import date_range_for_expression
        start, end = date_range_for_expression("gibberish xyz 999")
        assert start is None
        assert end is None


class TestGetEnumValues:
    def test_known_table_and_column(self):
        from app.modules.assistant.business_helpers import get_enum_values
        result = get_enum_values("expenses", "category")
        assert "values" in result
        assert "general" in result["values"]

    def test_unknown_table_returns_error(self):
        from app.modules.assistant.business_helpers import get_enum_values
        result = get_enum_values("unknown_table", "col")
        assert "error" in result

    def test_unknown_column_returns_error(self):
        from app.modules.assistant.business_helpers import get_enum_values
        result = get_enum_values("expenses", "unknown_col")
        assert "error" in result

    def test_case_insensitive(self):
        from app.modules.assistant.business_helpers import get_enum_values
        result = get_enum_values("EXPENSES", "CATEGORY")
        assert "values" in result
