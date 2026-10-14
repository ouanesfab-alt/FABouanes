"""Tests de couverture ciblés — Lot 3.

Couvre: rate_limit_store.py (_InMemoryRateLimitStore), sql_tools.py (serialize_for_json),
        models_pkg/users.py, models_pkg/expenses.py, models_pkg/clients.py validators
"""
from __future__ import annotations

import time
from decimal import Decimal
from datetime import date, datetime


# ── rate_limit_store.py (_InMemoryRateLimitStore, 67% → target ~90%) ─


def test_in_memory_store_consume_under_limit():
    """Consume under limit returns True."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    assert store.consume("test_key", limit=5, window_seconds=60.0) is True


def test_in_memory_store_consume_at_limit():
    """Consume at limit returns False."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    for _ in range(5):
        store.consume("test_key", limit=5, window_seconds=60.0)
    assert store.consume("test_key", limit=5, window_seconds=60.0) is False


def test_in_memory_store_record_failure():
    """Record failure adds attempts."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    for _ in range(3):
        store.record_failure("user:login:alice")
    assert len(store._attempts["user:login:alice"]) == 3


def test_in_memory_store_record_failure_caps_at_100():
    """Record failure caps entries at 100."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    for _ in range(110):
        store.record_failure("key")
    assert len(store._attempts["key"]) == 100


def test_in_memory_store_is_locked_out_false():
    """Not locked out with no failures."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    assert store.is_locked_out("key", max_attempts=5, window_s=60.0, lockout_s=30.0) is False


def test_in_memory_store_is_locked_out_true():
    """Locked out after too many failures."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    for _ in range(6):
        store.record_failure("user:login:bob")
    assert store.is_locked_out("user:login:bob", max_attempts=5, window_s=300.0, lockout_s=30.0) is True


def test_in_memory_store_is_locked_out_explicit_lockout():
    """Explicit lockout (via _lockouts dict) returns True."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    store._lockouts["key"] = time.monotonic() + 999  # locked for 999 seconds
    assert store.is_locked_out("key", max_attempts=5, window_s=60.0, lockout_s=30.0) is True


def test_in_memory_store_clear():
    """Clear removes data for a key."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    store.consume("test_key", 10, 60.0)
    store.record_failure("test_key")
    store.clear("test_key")
    assert "test_key" not in store._attempts


def test_in_memory_store_clear_user():
    """clear_user removes all keys containing username."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    store.consume("login:alice:ip1", 10, 60.0)
    store.consume("login:alice:ip2", 10, 60.0)
    store.consume("login:bob:ip1", 10, 60.0)
    store._lockouts["login:alice:ip1"] = time.monotonic() + 100
    store.clear_user("alice")
    assert "login:alice:ip1" not in store._attempts
    assert "login:alice:ip2" not in store._attempts
    assert "login:bob:ip1" in store._attempts


def test_in_memory_store_clear_all():
    """clear_all removes everything."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    store.consume("a", 10, 60.0)
    store.consume("b", 10, 60.0)
    store.clear_all()
    assert len(store._attempts) == 0
    assert len(store._lockouts) == 0


def test_in_memory_store_purge_removes_old():
    """Purge removes entries outside window."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore
    store = _InMemoryRateLimitStore()
    # Insert old entries by manipulating _attempts directly
    now = time.monotonic()
    store._attempts["key"] = [now - 120, now - 90, now - 5]
    # Consume triggers purge (window=60s should remove first 2)
    store.consume("key", 10, 60.0)
    # Should have 2 entries: the recent one + the new consume
    assert len(store._attempts["key"]) == 2


# ── sql_tools.py (serialize_for_json, 66% → covers L17-29) ─────────


def test_serialize_for_json_decimal_integer():
    """Decimal with no fractional part converts to int."""
    from app.modules.assistant.sql_tools import serialize_for_json
    assert serialize_for_json(Decimal("42")) == 42
    assert isinstance(serialize_for_json(Decimal("42")), int)


def test_serialize_for_json_decimal_float():
    """Decimal with fractional part converts to float."""
    from app.modules.assistant.sql_tools import serialize_for_json
    result = serialize_for_json(Decimal("12.75"))
    assert result == 12.75
    assert isinstance(result, float)


def test_serialize_for_json_date():
    """Date converts to ISO string."""
    from app.modules.assistant.sql_tools import serialize_for_json
    assert serialize_for_json(date(2025, 6, 15)) == "2025-06-15"


def test_serialize_for_json_datetime():
    """Datetime converts to ISO string."""
    from app.modules.assistant.sql_tools import serialize_for_json
    result = serialize_for_json(datetime(2025, 6, 15, 14, 30))
    assert "2025-06-15" in result
    assert "14:30" in result


def test_serialize_for_json_dict():
    """Dict values are recursively serialized."""
    from app.modules.assistant.sql_tools import serialize_for_json
    result = serialize_for_json({"total": Decimal("100.50"), "date": date(2025, 1, 1)})
    assert result == {"total": 100.50, "date": "2025-01-01"}


def test_serialize_for_json_list():
    """List values are recursively serialized."""
    from app.modules.assistant.sql_tools import serialize_for_json
    result = serialize_for_json([Decimal("1"), Decimal("2.5"), "hello"])
    assert result == [1, 2.5, "hello"]


def test_serialize_for_json_passthrough():
    """Non-special types pass through unchanged."""
    from app.modules.assistant.sql_tools import serialize_for_json
    assert serialize_for_json("hello") == "hello"
    assert serialize_for_json(42) == 42
    assert serialize_for_json(None) is None


# ── models_pkg/users.py validators (88% → target ~95%) ─────────────


def test_user_model_tablename():
    """Users model tablename is correct."""
    from app.core.models_pkg.users import User
    assert User.__tablename__ == "users"


# ── models_pkg/expenses.py validators (88%) ─────────────────────────


def test_expense_model_coerce_amount_from_float():
    """Expense._coerce_amount converts float to Decimal."""
    from app.core.models_pkg.expenses import Expense
    assert Expense._coerce_amount(15.5) == Decimal("15.5")


def test_expense_model_coerce_amount_passthrough():
    """Expense._coerce_amount passes Decimal through."""
    from app.core.models_pkg.expenses import Expense
    d = Decimal("20")
    assert Expense._coerce_amount(d) is d


# ── models_pkg/clients.py validators (95%) ──────────────────────────


def test_client_opening_credit_coerce_float():
    """Client._coerce_opening_credit converts float to Decimal."""
    from app.core.models_pkg.clients import Client
    assert Client._coerce_opening_credit(99.99) == Decimal("99.99")


def test_client_opening_credit_coerce_passthrough():
    """Client._coerce_opening_credit passes Decimal through."""
    from app.core.models_pkg.clients import Client
    d = Decimal("50")
    assert Client._coerce_opening_credit(d) is d


# ── models_pkg/sales.py validators (90% → target ~95%) ──────────────


def test_sale_coerce_sale_type_from_string():
    """Sale._coerce_sale_type converts string to SaleType enum."""
    from app.core.models_pkg.sales import Sale, SaleType
    result = Sale._coerce_sale_type("cash")
    assert result == SaleType.CASH


def test_sale_coerce_sale_type_passthrough():
    """Sale._coerce_sale_type passes SaleType enum through."""
    from app.core.models_pkg.sales import Sale, SaleType
    val = SaleType.CASH
    assert Sale._coerce_sale_type(val) is val


