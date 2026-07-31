"""Tests unitaires approfondis pour app/core/db_helpers/manager.py (Couverture > 90%)."""
from __future__ import annotations

import sqlite3
from unittest import mock
from decimal import Decimal
import pytest

from app.core.db_helpers.manager import (
    db_manager,
    CompatConnection,
    CompatCursor,
    CompatRow,
    _wrap_rows,
    _clean_params,
    DatabaseManager,
)


def test_compat_row_and_wrap_rows():
    row = CompatRow({"a": 10, "b": "hello"})
    assert row["a"] == 10
    assert row[0] == 10
    assert row[1] == "hello"

    cols_desc = [("id", None), ("name", None)]
    raw_rows = [(1, "alice"), (2, "bob")]
    wrapped = _wrap_rows(raw_rows, cols_desc)
    assert len(wrapped) == 2
    assert wrapped[0]["id"] == 1
    assert wrapped[0]["name"] == "alice"

    assert _wrap_rows(raw_rows, None) == raw_rows


def test_clean_params():
    assert _clean_params(None) is None
    assert _clean_params(()) == ()
    assert _clean_params({"a": 3.14}) == {"a": Decimal("3.14")}
    cleaned_tuple = _clean_params((1, 2.5, [1.1, 2], (3.3, 4)))
    assert isinstance(cleaned_tuple[1], Decimal)
    assert cleaned_tuple[1] == Decimal("2.5")


def test_compat_connection_and_cursor(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    c_conn = CompatConnection(conn)

    c_conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    c_conn.commit()

    c_conn.execute("INSERT INTO test VALUES (1, 'alice')")
    c_conn.commit()

    cursor = c_conn.execute("SELECT id, name FROM test ORDER BY id")
    row1 = cursor.fetchone()
    assert row1 is not None

    cursor.close()
    c_conn.close()


def test_database_manager_methods():
    mgr = DatabaseManager()
    assert mgr.sqlalchemy_database_url("postgresql://u:p@localhost/db") == "postgresql+pg8000://u:p@localhost/db"
    assert mgr.sqlalchemy_database_url("sqlite:///foo.db") == "sqlite:///foo.db"

    assert mgr._env_int("NON_EXISTENT_VAR_123", 42) == 42
    assert mgr._env_int("NON_EXISTENT_VAR_123", 42, minimum=50) == 50

    q_count = "SELECT count(*) FROM sales"
    assert mgr._guard_pagination(q_count) == q_count

    q_select = "SELECT * FROM sales"
    guarded = mgr._guard_pagination(q_select)
    assert "LIMIT" in guarded

    mgr._invalidate_after_write("INSERT INTO clients (name) VALUES ('test')")
    mgr._record_performance_event("sql", "SELECT 1", 150.0, "details")
    assert mgr.pending_performance_event_count() > 0


def test_database_manager_settings_and_transactions():
    assert db_manager is not None
    assert hasattr(db_manager, "execute_db")
    assert db_manager.pending_performance_event_count() >= 0

    with mock.patch.object(db_manager, "query_db", return_value={"value": "bar"}):
        val = db_manager.get_setting("foo", "default")
        assert val == "bar"

    with mock.patch.object(db_manager, "query_db", side_effect=Exception("DB Error")):
        val_default = db_manager.get_setting("missing", "default_val")
        assert val_default == "default_val"
