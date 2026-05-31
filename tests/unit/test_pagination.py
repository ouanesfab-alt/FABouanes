"""Tests for app.utils.pagination — parse_pagination, cursor helpers, and paginate_sequence.

All helpers tested here are pure functions (or only depend on
``app.core.request_state`` which is a lightweight ContextVar module).
No database is required.
"""
from __future__ import annotations

import pytest

from app.utils.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    paginate_sequence,
    parse_pagination,
)


# ======================================================================
# parse_pagination
# ======================================================================


class TestParsePagination:
    """Tests for parse_pagination(args)."""

    def test_defaults(self) -> None:
        page, page_size, offset = parse_pagination({})
        assert page == 1
        assert page_size == DEFAULT_PAGE_SIZE
        assert offset == 0

    def test_none_args_uses_defaults(self) -> None:
        page, page_size, offset = parse_pagination(None)
        assert page == 1
        assert page_size == DEFAULT_PAGE_SIZE
        assert offset == 0

    def test_custom_page_and_size(self) -> None:
        page, page_size, offset = parse_pagination({"page": "3", "page_size": "20"})
        assert page == 3
        assert page_size == 20
        assert offset == 40

    def test_page_one_offset_is_zero(self) -> None:
        _, _, offset = parse_pagination({"page": "1", "page_size": "10"})
        assert offset == 0

    def test_negative_page_clamped_to_one(self) -> None:
        page, _, _ = parse_pagination({"page": "-5"})
        assert page == 1

    def test_zero_page_clamped_to_one(self) -> None:
        page, _, _ = parse_pagination({"page": "0"})
        assert page == 1

    def test_page_size_clamped_to_max(self) -> None:
        _, page_size, _ = parse_pagination({"page_size": "999"})
        assert page_size == MAX_PAGE_SIZE

    def test_page_size_zero_clamped_to_one(self) -> None:
        _, page_size, _ = parse_pagination({"page_size": "0"})
        assert page_size == 1

    def test_negative_page_size_clamped_to_one(self) -> None:
        _, page_size, _ = parse_pagination({"page_size": "-10"})
        assert page_size == 1

    def test_invalid_page_uses_default(self) -> None:
        page, _, _ = parse_pagination({"page": "abc"})
        assert page == 1

    def test_invalid_page_size_uses_default(self) -> None:
        _, page_size, _ = parse_pagination({"page_size": "xyz"})
        assert page_size == DEFAULT_PAGE_SIZE

    def test_both_invalid_use_defaults(self) -> None:
        page, page_size, _ = parse_pagination({"page": "abc", "page_size": "xyz"})
        assert page == 1
        assert page_size == DEFAULT_PAGE_SIZE

    def test_custom_default_page_size(self) -> None:
        _, page_size, _ = parse_pagination({}, default_page_size=25)
        assert page_size == 25

    def test_integer_values_instead_of_strings(self) -> None:
        """The function should also work when args values are already ints."""
        page, page_size, offset = parse_pagination({"page": 2, "page_size": 15})
        assert page == 2
        assert page_size == 15
        assert offset == 15





# ======================================================================
# paginate_sequence
# ======================================================================


class TestPaginateSequence:
    """Tests for paginate_sequence(rows, args, path)."""

    def test_first_page(self) -> None:
        rows = list(range(100))
        result, ctx = paginate_sequence(rows, {"page": "1", "page_size": "10"}, "/test")
        assert result == list(range(10))
        assert ctx["total"] == 100
        assert ctx["has_next"] is True
        assert ctx["has_prev"] is False

    def test_middle_page(self) -> None:
        rows = list(range(100))
        result, ctx = paginate_sequence(rows, {"page": "5", "page_size": "10"}, "/test")
        assert result == list(range(40, 50))
        assert ctx["has_next"] is True
        assert ctx["has_prev"] is True

    def test_last_page(self) -> None:
        rows = list(range(25))
        result, ctx = paginate_sequence(rows, {"page": "3", "page_size": "10"}, "/test")
        assert result == [20, 21, 22, 23, 24]
        assert ctx["has_next"] is False
        assert ctx["has_prev"] is True

    def test_empty_rows(self) -> None:
        result, ctx = paginate_sequence([], {"page": "1", "page_size": "10"}, "/test")
        assert result == []
        assert ctx["total"] == 0
        assert ctx["has_next"] is False
        assert ctx["has_prev"] is False

    def test_single_page(self) -> None:
        rows = list(range(5))
        result, ctx = paginate_sequence(rows, {"page": "1", "page_size": "10"}, "/test")
        assert result == [0, 1, 2, 3, 4]
        assert ctx["has_next"] is False
        assert ctx["has_prev"] is False

    def test_beyond_last_page(self) -> None:
        rows = list(range(10))
        result, ctx = paginate_sequence(rows, {"page": "99", "page_size": "10"}, "/test")
        assert result == []

    def test_page_and_page_size_in_context(self) -> None:
        rows = list(range(50))
        _, ctx = paginate_sequence(rows, {"page": "2", "page_size": "20"}, "/items")
        assert ctx["page"] == 2
        assert ctx["page_size"] == 20
