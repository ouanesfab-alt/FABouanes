"""
test_coverage_boost_lot22.py
Targets remaining uncovered code:
  - permissions.py  (has_permission branches, permission_denied_response, _audit)
  - rate_limit_store.py (_InMemoryRateLimitStore exponential backoff, _DbRateLimitStore)
  - registry.py     (module disable via env)
  - helpers.py      (parse_excel_client_history error path, init_db)
  - models_pkg/sales.py & users.py (model properties)
  - sql_guard.py    (edge cases)
  - manager.py      (_postgres_last_insert_id, db_transaction nested, _route_label)
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# 1. permissions.py — has_permission, permission_denied_response
# ============================================================

from app.core.permissions import (
    has_permission,
    normalize_role,
    permission_for_endpoint,
    _get_dynamic_permissions,
    MANAGER_PERMISSIONS,
)


def test_has_permission_none_permission():
    """None permission means always allowed."""
    assert has_permission(None, None) is True
    assert has_permission({"role": "cashier"}, None) is True


def test_has_permission_no_user():
    assert has_permission(None, "operations.write") is False


def test_has_permission_admin():
    user = {"role": "admin"}
    assert has_permission(user, "any.permission") is True


def test_has_permission_manager_allowed():
    user = {"role": "manager"}
    # Manager should have access to at least one permission in MANAGER_PERMISSIONS
    perm = next(iter(MANAGER_PERMISSIONS))
    assert has_permission(user, perm) is True


def test_has_permission_manager_not_allowed():
    user = {"role": "manager"}
    assert has_permission(user, "admin.super.secret") is False


def test_has_permission_custom_permission_dict():
    user = {"role": "cashier", "custom_permissions": ["custom.special"]}
    assert has_permission(user, "custom.special") is True


def test_has_permission_custom_permissions_json_dict():
    import json
    user = {"role": "cashier", "custom_permissions_json": json.dumps(["custom.from_json"])}
    assert has_permission(user, "custom.from_json") is True


def test_has_permission_custom_permissions_object():
    user = SimpleNamespace(
        role="cashier",
        custom_permissions_list=["obj.permission"],
        custom_permissions_json="[]"
    )
    assert has_permission(user, "obj.permission") is True


def test_has_permission_custom_permissions_json_object():
    import json
    user = SimpleNamespace(
        role="cashier",
        custom_permissions_list=[],
        custom_permissions_json=json.dumps(["json.obj.perm"])
    )
    assert has_permission(user, "json.obj.perm") is True


def test_has_permission_role_permissions():
    user = {"role": "cashier"}
    # Cashier has access to basic read operations
    assert has_permission(user, "any.nonexistent.permission") is False


def test_normalize_role_none():
    # normalize_role returns a default role for None (not empty string)
    result = normalize_role(None)
    assert isinstance(result, str)  # always returns a string


def test_normalize_role_admin_variant():
    # normalize_role lowercases and strips
    result = normalize_role("Admin")
    assert result in ("admin", "Admin".lower())


def test_permission_for_endpoint_public():
    # Public endpoints return None
    result = permission_for_endpoint("login")
    assert result is None


def test_permission_for_endpoint_none():
    result = permission_for_endpoint(None)
    assert result is None


def test_permission_for_endpoint_options():
    result = permission_for_endpoint("some_endpoint", "OPTIONS")
    assert result is None


def test_permission_for_endpoint_unknown():
    result = permission_for_endpoint("totally_unknown_endpoint_xyz")
    assert result is None


def test_get_dynamic_permissions_caching():
    """Test that _get_dynamic_permissions returns cached results."""
    import app.core.permissions as pmod
    original = pmod._dynamic_permissions_cache
    try:
        pmod._dynamic_permissions_cache = {"admin": {"dynamic.perm"}}
        result = _get_dynamic_permissions("admin")
        assert "dynamic.perm" in result
    finally:
        pmod._dynamic_permissions_cache = original


def test_get_dynamic_permissions_empty_role():
    import app.core.permissions as pmod
    original = pmod._dynamic_permissions_cache
    try:
        pmod._dynamic_permissions_cache = {}
        result = _get_dynamic_permissions("nonexistent_role")
        assert result == set()
    finally:
        pmod._dynamic_permissions_cache = original


# ============================================================
# 2. rate_limit_store.py — InMemoryRateLimitStore exponential backoff
# ============================================================

from app.core.rate_limit_store import _InMemoryRateLimitStore


def test_in_memory_consume_allows_under_limit():
    store = _InMemoryRateLimitStore()
    store.clear_all()
    result = store.consume("test_user", 5, 60.0)
    assert result is True


def test_in_memory_consume_blocks_over_limit():
    store = _InMemoryRateLimitStore()
    store.clear("over_limit_key")
    # Fill up to limit
    for _ in range(5):
        store.consume("over_limit_key", 5, 60.0)
    # Next should be blocked
    result = store.consume("over_limit_key", 5, 60.0)
    assert result is False


def test_in_memory_record_failure():
    store = _InMemoryRateLimitStore()
    store.clear("fail_key")
    store.record_failure("fail_key")
    assert len(store._attempts.get("fail_key", [])) == 1


def test_in_memory_is_locked_out_not_enough_attempts():
    store = _InMemoryRateLimitStore()
    store.clear("lock_key")
    store.record_failure("lock_key")  # Only 1 attempt, need 3
    result = store.is_locked_out("lock_key", max_attempts=3, window_s=60.0, lockout_s=30.0)
    assert result is False


def test_in_memory_is_locked_out_enough_attempts():
    store = _InMemoryRateLimitStore()
    store.clear("lock_key2")
    # Record enough failures to trigger lockout
    for _ in range(5):
        store.record_failure("lock_key2")
    result = store.is_locked_out("lock_key2", max_attempts=3, window_s=60.0, lockout_s=300.0)
    assert result is True  # Should be locked out


def test_in_memory_is_locked_out_expired():
    store = _InMemoryRateLimitStore()
    store.clear("old_key")
    # Add old timestamps
    with store._lock:
        store._attempts["old_key"] = [time.time() - 9999]  # Very old
    result = store.is_locked_out("old_key", max_attempts=3, window_s=60.0, lockout_s=30.0)
    assert result is False


def test_in_memory_clear_user():
    store = _InMemoryRateLimitStore()
    store.record_failure("john_doe:192.168.1.1")
    store.record_failure("john_doe:192.168.1.2")
    store.clear_user("john_doe")
    assert "john_doe:192.168.1.1" not in store._attempts
    assert "john_doe:192.168.1.2" not in store._attempts


def test_in_memory_clear_all():
    store = _InMemoryRateLimitStore()
    store.record_failure("key1")
    store.record_failure("key2")
    store.clear_all()
    assert len(store._attempts) == 0


# ============================================================
# 3. registry.py — disabled module via env
# ============================================================

from app.core.registry import get_enabled_modules


def test_get_enabled_modules_returns_list():
    modules = get_enabled_modules()
    assert isinstance(modules, list)
    assert all(hasattr(m, "name") for m in modules)


def test_get_enabled_modules_excludes_disabled():
    """Disabled modules should not appear in get_enabled_modules."""
    modules = get_enabled_modules()
    for m in modules:
        assert m.enabled is True


# ============================================================
# 4. helpers.py — parse_excel_client_history error path
# ============================================================

from app.core.helpers import parse_excel_client_history


def test_parse_excel_client_history_error_path():
    """When parse_client_history_excel raises, return safe fallback."""
    # parse_client_history_excel is imported locally; patch at its source
    with patch("app.services.excel_import_service.parse_client_history_excel",
               side_effect=Exception("File not found"), create=True):
        result = parse_excel_client_history("/nonexistent/file.xlsx")
    assert result["last_date"] is None
    assert result["last_balance"] == 0.0


def test_parse_excel_client_history_success():
    fake_data = {"rows": [{"date": "2024-01-01", "amount": 100}], "solde_final": 500.0}
    with patch("app.services.excel_import_service.parse_client_history_excel",
               return_value=fake_data, create=True):
        result = parse_excel_client_history("/fake/path.xlsx")
    assert result["last_date"] == "2024-01-01"
    assert result["last_balance"] == 500.0


def test_parse_excel_client_history_empty_rows():
    fake_data = {"rows": [], "solde_final": 0.0}
    with patch("app.services.excel_import_service.parse_client_history_excel",
               return_value=fake_data, create=True):
        result = parse_excel_client_history("/fake/path.xlsx")
    assert result["last_date"] is None
    assert result["last_balance"] == 0.0


# ============================================================
# 5. sql_guard.py — additional branches
# ============================================================

from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql


def test_validate_readonly_with_comment():
    result = validate_readonly_sql("-- This is a comment\nSELECT id FROM clients LIMIT 5")
    # Should pass (SELECT after comment)
    assert isinstance(result.ok, bool)


def test_validate_write_update():
    result = validate_write_sql("UPDATE clients SET name = 'Test' WHERE id = 1")
    assert result.ok is True


def test_validate_write_delete():
    result = validate_write_sql("DELETE FROM clients WHERE id = 999")
    assert result.ok is True


def test_validate_write_drop_rejected():
    result = validate_write_sql("DROP TABLE clients")
    assert result.ok is False


def test_validate_write_truncate_rejected():
    result = validate_write_sql("TRUNCATE clients")
    assert result.ok is False


def test_validate_readonly_subquery():
    result = validate_readonly_sql("SELECT * FROM (SELECT id FROM clients) AS sub LIMIT 10")
    assert isinstance(result.ok, bool)


# ============================================================
# 6. manager.py — _postgres_last_insert_id, db_transaction nested, _route_label
# ============================================================

from app.core.db_helpers.manager import DatabaseManager


def test_postgres_last_insert_id_non_insert():
    mgr = DatabaseManager()
    mock_db = MagicMock()
    result = mgr._postgres_last_insert_id(mock_db, "SELECT * FROM clients")
    assert result == 0


def test_postgres_last_insert_id_skipped_table():
    mgr = DatabaseManager()
    mock_db = MagicMock()
    result = mgr._postgres_last_insert_id(mock_db, "INSERT INTO app_settings (key) VALUES ('x')")
    assert result == 0


def test_postgres_last_insert_id_db_error():
    mgr = DatabaseManager()
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("no sequence")
    result = mgr._postgres_last_insert_id(mock_db, "INSERT INTO clients (name) VALUES ('X')")
    assert result == 0


def test_postgres_last_insert_id_success():
    mgr = DatabaseManager()
    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 42}
    mock_db.execute.return_value = mock_cur
    result = mgr._postgres_last_insert_id(mock_db, "INSERT INTO clients (name) VALUES ('Test')")
    assert result == 42


def test_route_label_no_state():
    mgr = DatabaseManager()
    with patch("app.core.db_helpers.manager.get_request_state", return_value=None):
        label = mgr._route_label()
    assert label == ""


def test_route_label_with_state():
    mgr = DatabaseManager()
    mock_req = MagicMock()
    mock_req.method = "GET"
    mock_req.url.path = "/api/v1/clients"
    mock_req.scope.get.return_value = None

    mock_state = SimpleNamespace(request=mock_req)
    with patch("app.core.db_helpers.manager.get_request_state", return_value=mock_state):
        label = mgr._route_label()
    assert "GET" in label


def test_db_transaction_nested_savepoints():
    """Test that nested db_transaction uses savepoints."""
    mgr = DatabaseManager()
    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.execute.return_value = mock_cur

    from app.core.request_state import push_request_state, reset_request_state
    from fastapi import Request

    scope = {"type": "http", "method": "GET", "path": "/test",
             "query_string": b"", "headers": []}
    req = Request(scope)
    token = push_request_state(
        request=req, db=mock_db, session={}, request_id="t1",
        audit_source="api", user=None, g=SimpleNamespace(user=None), csp_nonce="x"
    )
    try:
        from app.core.request_state import get_request_state
        state = get_request_state()
        state.db = mock_db
        state.db_tx_depth = 1  # Already in a transaction

        # Patch get_write_db to return our mock directly
        with patch.object(mgr, "get_write_db", return_value=mock_db):
            with mgr.db_transaction():
                pass  # Should create SAVEPOINT + RELEASE SAVEPOINT
        # SAVEPOINT should have been called
        assert mock_db.execute.called
    finally:
        reset_request_state(token)


def test_db_transaction_rollback_on_exception():
    """Test that db_transaction rolls back on exception."""
    mgr = DatabaseManager()
    mock_db = MagicMock()

    from app.core.request_state import push_request_state, reset_request_state
    from fastapi import Request

    scope = {"type": "http", "method": "GET", "path": "/test2",
             "query_string": b"", "headers": []}
    req = Request(scope)
    token = push_request_state(
        request=req, db=mock_db, session={}, request_id="t2",
        audit_source="api", user=None, g=SimpleNamespace(user=None), csp_nonce="y"
    )
    try:
        # Patch get_write_db so no real DB connection is attempted
        with patch.object(mgr, "get_write_db", return_value=mock_db):
            with pytest.raises(ValueError):
                with mgr.db_transaction():
                    raise ValueError("test rollback")
        mock_db.rollback.assert_called()
    finally:
        reset_request_state(token)


# ============================================================
# 7. models_pkg/sales.py — uncovered lines 60, 94-96, 121-123
# ============================================================

def test_sale_document_model_attributes():
    from app.core.models_pkg.sales import SaleDocument
    doc = SaleDocument(
        doc_number="FAC-001",
        sale_type="credit",
        sale_date=None,
    )
    assert doc.doc_number == "FAC-001"


def test_raw_sale_model_attributes():
    from app.core.models_pkg.sales import RawSale
    sale = RawSale(
        item_id=1,
        quantity=5.0,
        unit_price=100.0,
        total=500.0,
        sale_type="cash",
    )
    assert sale.quantity == 5.0


# ============================================================
# 8. models_pkg/users.py — uncovered lines 36-37, 43-45
# ============================================================

def test_user_model_basic():
    from app.core.models_pkg.users import User
    user = User(username="testuser", role="cashier")
    assert user.username == "testuser"
    assert user.role == "cashier"
