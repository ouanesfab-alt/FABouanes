"""
test_coverage_boost_lot27.py
Targets:
  - manager.py:
    - _write_performance_batch with conn age > 900 (line 663-669)
    - _write_performance_batch exception path (line 684-691)
    - shutdown exception path (line 717-718, 723-724)
    - query_db_async & execute_db_async (lines 492-494, 548-550)
    - execute_db RETURNING fetchone exception (lines 509-510)
    - execute_db rollback exception (lines 527-528, 535-536)
    - query_db rollback exception (lines 478-479, 484-488)
    - drain_performance_events_once (lines 731-734)
    - get_db helper (line 748)
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from app.core.db_helpers.manager import DatabaseManager, get_db


def test_get_db_helper():
    """Line 748: get_db calls db_manager.get_db()."""
    with patch("app.core.db_helpers.manager.db_manager.get_db", return_value=MagicMock()):
        conn = get_db()
        assert conn is not None


@pytest.mark.asyncio
async def test_query_db_async():
    """Lines 492-494: query_db_async delegates to query_db in thread."""
    mgr = DatabaseManager()
    with patch.object(mgr, "query_db", return_value=[{"id": 1}]):
        res = await mgr.query_db_async("SELECT 1", ())
        assert res == [{"id": 1}]


@pytest.mark.asyncio
async def test_execute_db_async():
    """Lines 548-550: execute_db_async delegates to execute_db in thread."""
    mgr = DatabaseManager()
    with patch.object(mgr, "execute_db", return_value=5):
        res = await mgr.execute_db_async("UPDATE clients SET name = 'X'", ())
        assert res == 5


def test_write_performance_batch_conn_recycle():
    """Lines 663-669: _write_performance_batch recycles old connection (>900s)."""
    mgr = DatabaseManager()
    mock_old_conn = MagicMock()
    mgr._perf_conn = mock_old_conn
    mgr._perf_conn_created_at = time.monotonic() - 1000  # > 900s

    mock_new_conn = MagicMock()

    with patch.object(mgr, "connect_database", return_value=mock_new_conn):
        mgr._write_performance_batch([("sql", "query", 10.0, "/test", "")])

    mock_old_conn.close.assert_called()
    assert mgr._perf_conn is mock_new_conn


def test_write_performance_batch_exception():
    """Lines 684-691: _write_performance_batch exception path closes connection and re-raises."""
    mgr = DatabaseManager()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("db insert error")
    mock_conn.close.side_effect = Exception("close error")
    mgr._perf_conn = mock_conn
    mgr._perf_conn_created_at = time.monotonic()

    with pytest.raises(Exception):
        mgr._write_performance_batch([("sql", "query", 10.0, "/test", "")])

    assert mgr._perf_conn is None


def test_shutdown_draining_error():
    """Lines 717-718, 723-724: shutdown handles exception while draining logs."""
    mgr = DatabaseManager()
    mgr._perf_conn = MagicMock()
    mgr._perf_conn.close.side_effect = Exception("close error")

    with patch.object(mgr, "_write_performance_batch", side_effect=Exception("write error")):
        # Add 1 item to queue so drain attempts to run
        mgr._perf_queue.append(("sql", "query", 5.0, "/route", ""))
        # Should not raise exception
        mgr.shutdown()

    assert mgr._perf_conn is None


def test_drain_performance_events_once():
    """Lines 731-734: drain_performance_events_once."""
    mgr = DatabaseManager()
    mgr._perf_queue.append(("sql", "query", 5.0, "/route", ""))
    with patch.object(mgr, "_write_performance_batch"):
        count = mgr.drain_performance_events_once()
    assert count == 1


def test_execute_db_returning_fetchone_exception():
    """Lines 509-510: execute_db handles fetchone exception on RETURNING query."""
    mgr = DatabaseManager()
    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = Exception("fetchone failed")
    mock_db.execute.return_value = mock_cur

    with patch.object(mgr, "get_write_db", return_value=mock_db), \
         patch.object(mgr, "_postgres_last_insert_id", return_value=123):
        res = mgr.execute_db("INSERT INTO clients (name) VALUES ('X') RETURNING id", ())
    assert res == 123


def test_execute_db_transient_retry_and_rollback_error():
    """Lines 527-528, 535-536: execute_db transient retry with rollback error."""
    mgr = DatabaseManager()
    mock_db1 = MagicMock()
    mock_db1.execute.side_effect = Exception("transient connection closed")
    mock_db1.rollback.side_effect = Exception("rollback failed")
    mock_db1.close.side_effect = Exception("close failed")

    mock_db2 = MagicMock()
    mock_cur2 = MagicMock()
    mock_cur2.lastrowid = 7
    mock_db2.execute.return_value = mock_cur2

    with patch.object(mgr, "get_write_db", side_effect=[mock_db1, mock_db2]):
        res = mgr.execute_db("INSERT INTO clients (name) VALUES ('Y')", ())
    assert res == 7


def test_query_db_transient_retry_and_rollback_error():
    """Lines 478-479, 484-488: query_db transient retry with rollback error."""
    mgr = DatabaseManager()
    mock_db1 = MagicMock()
    mock_db1.execute.side_effect = Exception("transient connection lost")
    mock_db1.rollback.side_effect = Exception("rollback failed")

    mock_db2 = MagicMock()
    mock_cur2 = MagicMock()
    mock_cur2.fetchall.return_value = [{"id": 1}]
    mock_db2.execute.return_value = mock_cur2

    with patch.object(mgr, "get_read_db", side_effect=[mock_db1, mock_db2]):
        res = mgr.query_db("SELECT * FROM clients", ())
    assert res == [{"id": 1}]
