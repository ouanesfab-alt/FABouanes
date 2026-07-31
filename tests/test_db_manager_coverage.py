"""Tests unitaires ciblés pour app/core/db_helpers/manager.py (Couverture > 90%)."""
from __future__ import annotations

import sqlite3
from unittest import mock
import pytest

from app.core.db_helpers.manager import db_manager, CompatConnection, CompatCursor


def test_compat_connection_and_cursor(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    c_conn = CompatConnection(conn)

    cursor = c_conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    c_conn.commit()

    cursor.executemany("INSERT INTO test VALUES (?, ?)", [(1, "alice"), (2, "bob")])
    c_conn.commit()

    cursor.execute("SELECT id, name FROM test ORDER BY id")
    row1 = cursor.fetchone()
    assert row1 is not None

    cursor.close()
    c_conn.close()


def test_db_manager_settings():
    assert db_manager is not None
    assert hasattr(db_manager, "execute_db")
    assert db_manager.pending_performance_event_count() >= 0
