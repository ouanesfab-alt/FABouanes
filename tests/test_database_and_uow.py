"""Comprehensive tests for Database layer, Connection pool, and Unit of Work (app/core/database.py & app/core/uow.py)."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from unittest import mock

import pytest
from sqlalchemy import column, table

from app.core.database import (
    CompatConnection,
    CompatCursor,
    CompatRow,
    DatabaseManager,
    _clean_params,
    _wrap_rows,
    db_manager,
    db_task,
    db_transaction,
    execute_db,
    execute_db_async,
    execute_sa,
    get_setting,
    is_sqlite,
    list_columns,
    postgres_pool_status,
    query_db_async,
    set_setting,
)
from app.core.uow import unit_of_work, with_uow


def test_compat_row():
    row_data = {"id": 1, "name": "Test Item", "price": 10.5}
    row = CompatRow(row_data)

    assert row["id"] == 1
    assert row["name"] == "Test Item"
    assert row[0] == 1
    assert row[1] == "Test Item"
    assert row[2] == 10.5


def test_clean_params():
    params = (1.5, [2.5, "keep"], {"a": 3.5})
    cleaned = _clean_params(params)
    assert cleaned[0] == Decimal("1.5")
    assert cleaned[1][0] == Decimal("2.5")
    assert cleaned[2]["a"] == Decimal("3.5")

    cleaned_tuple = _clean_params((10.25,))
    assert cleaned_tuple == (Decimal("10.25"),)

    assert _clean_params(None) is None
    assert _clean_params(()) == ()


def test_wrap_rows():
    rows = [(1, "Alice"), (2, "Bob")]
    desc = [("id",), ("name",)]
    wrapped = _wrap_rows(rows, desc)
    assert len(wrapped) == 2
    assert wrapped[0]["name"] == "Alice"
    assert wrapped[1][0] == 2

    assert _wrap_rows(rows, None) == rows


def test_compat_cursor():
    mock_cursor = mock.MagicMock()
    mock_cursor.description = [("id",), ("name",)]
    mock_cursor.fetchall.return_value = [(1, "Alice")]
    mock_cursor.fetchone.return_value = (2, "Bob")
    mock_cursor.lastrowid = 123

    compat = CompatCursor(mock_cursor)
    assert compat.lastrowid == 123

    res_all = compat.fetchall()
    assert len(res_all) == 1
    assert res_all[0]["name"] == "Alice"

    res_one = compat.fetchone()
    assert res_one["name"] == "Bob"

    compat.close()
    assert mock_cursor.close.called

    mock_cursor.fetchone.return_value = None
    assert compat.fetchone() is None


def test_compat_connection_methods():
    mock_raw_conn = mock.MagicMock()
    mock_cursor = mock.MagicMock()
    mock_raw_conn.cursor.return_value = mock_cursor

    on_close_called = []
    reconnect_conn = mock.MagicMock()

    conn = CompatConnection(
        mock_raw_conn,
        dialect="postgres",
        on_close=lambda c: on_close_called.append(c),
        reconnect=lambda: reconnect_conn,
    )

    res_cur = conn.execute("SELECT 1")
    assert res_cur is not None
    mock_cursor.execute.assert_called_with("SELECT 1", ())

    conn.executescript("SELECT 1; SELECT 2;")
    assert mock_cursor.execute.call_count >= 2

    conn.commit()
    mock_raw_conn.commit.assert_called_once()
    conn.rollback()
    mock_raw_conn.rollback.assert_called_once()

    conn.close()
    assert len(on_close_called) == 1
    assert conn._closed is True
    conn.close()


def test_compat_connection_reconnect_retry():
    from sqlalchemy.exc import OperationalError

    mock_raw_conn1 = mock.MagicMock()
    mock_cur1 = mock.MagicMock()
    mock_cur1.execute.side_effect = OperationalError("connection lost", None, Exception("Connection closed"))
    mock_raw_conn1.cursor.return_value = mock_cur1

    mock_raw_conn2 = mock.MagicMock()
    mock_cur2 = mock.MagicMock()
    mock_raw_conn2.cursor.return_value = mock_cur2

    conn = CompatConnection(mock_raw_conn1, dialect="postgres", reconnect=lambda: mock_raw_conn2)

    res = conn.execute("SELECT 1")
    assert res is not None
    mock_cur2.execute.assert_called_with("SELECT 1", ())


def test_compat_connection_and_cursor_sqlite(tmp_path):
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


def test_db_manager_settings():
    with mock.patch.object(db_manager, "query_db") as mock_query, mock.patch.object(
        db_manager, "execute_db"
    ) as mock_execute:
        mock_query.return_value = {"value": "my_val_456"}

        set_setting("test_key_123", "my_val_456")
        mock_execute.assert_called_once()

        val = get_setting("test_key_123")
        assert val == "my_val_456"


def test_db_manager_settings_error():
    with mock.patch.object(db_manager, "query_db", side_effect=Exception("DB Error")):
        val_default = db_manager.get_setting("missing", "default_val")
        assert val_default == "default_val"


def test_db_transaction_and_queries():
    mock_conn = mock.MagicMock()
    mock_cursor = mock.MagicMock()
    mock_cursor.fetchone.return_value = {"id": 1, "name": "Row A"}
    mock_conn.execute.return_value = mock_cursor

    with mock.patch.object(db_manager, "get_write_db", return_value=mock_conn):
        with db_transaction() as tx:
            tx.execute("INSERT INTO dummy VALUES (%s)", ("Row A",))
            cur = tx.execute("SELECT * FROM dummy")
            row = cur.fetchone()
            assert row["name"] == "Row A"


def test_postgres_pool_status():
    mock_pool = mock.MagicMock()
    mock_pool.size.return_value = 10
    mock_pool.checkedin.return_value = 5
    mock_pool.checkedout.return_value = 2
    mock_pool.overflow.return_value = 1

    mock_engine = mock.MagicMock()
    mock_engine.pool = mock_pool

    with mock.patch.object(db_manager, "get_database_engine", return_value=mock_engine):
        status = postgres_pool_status("postgresql://mock")
        assert status["engine"] == "postgres"
        assert status["size"] == 10
        assert status["checkedin"] == 5


def test_list_columns():
    mock_conn = mock.MagicMock()
    mock_cursor = mock.MagicMock()
    mock_cursor.fetchall.return_value = [{"column_name": "id"}, {"column_name": "email"}]
    mock_conn.execute.return_value = mock_cursor

    cols = list_columns(mock_conn, "some_table")
    assert "id" in cols
    assert "email" in cols


def test_explain_query_plan():
    mock_conn = mock.MagicMock()
    mock_cursor = mock.MagicMock()
    mock_cursor.fetchall.return_value = [{"plan": "Explain plan details"}]
    mock_conn.execute.return_value = mock_cursor

    with mock.patch.object(db_manager, "get_db", return_value=mock_conn):
        plan = db_manager.explain_query_plan("SELECT 1")
        assert len(plan) == 1
        assert "plan" in plan[0]


@pytest.mark.asyncio
async def test_db_task_decorator():
    @db_task
    def mock_db_operation(x):
        return x * 2

    assert mock_db_operation(5) == 10
    assert mock_db_operation.sync(5) == 10

    res = await mock_db_operation.async_(5)
    assert res == 10


@pytest.mark.asyncio
async def test_async_query_and_execute():
    with mock.patch.object(db_manager, "query_db", return_value={"res": 1}), mock.patch.object(
        db_manager, "execute_db", return_value=42
    ):
        q_res = await query_db_async("SELECT 1", one=True)
        assert q_res == {"res": 1}

        e_res = await execute_db_async("INSERT INTO dummy VALUES (1)")
        assert e_res == 42


def test_execute_db_sync():
    with mock.patch.object(db_manager, "execute_db", return_value=5) as m_exec:
        res = execute_db("UPDATE test SET x=1", (1,))
        assert res == 5
        m_exec.assert_called_once_with("UPDATE test SET x=1", (1,))


def test_execute_sa_compilation():
    test_table = table("users", column("id"), column("name"))
    query = test_table.update().where(test_table.c.id == 42).values(name="alice")

    with mock.patch("app.core.database.execute_db", return_value=1) as m_exec:
        res = execute_sa(query)
        assert res == 1
        m_exec.assert_called_once()
        args = m_exec.call_args[0]
        assert "UPDATE users" in args[0]


def test_sqlalchemy_url_postgresql():
    mgr = DatabaseManager()
    r = mgr.sqlalchemy_database_url("postgresql://u:p@h/db")
    assert r.startswith("postgresql+pg8000://")
    assert "u:p@h/db" in r


def test_sqlalchemy_url_postgres():
    mgr = DatabaseManager()
    r = mgr.sqlalchemy_database_url("postgres://u:p@h/db")
    assert r.startswith("postgresql+pg8000://")


def test_sqlalchemy_url_other_unchanged():
    mgr = DatabaseManager()
    r = mgr.sqlalchemy_database_url("sqlite:///test.db")
    assert r == "sqlite:///test.db"


def test_guard_pagination_adds_limit():
    mgr = DatabaseManager()
    result = mgr._guard_pagination("SELECT id, name FROM clients")
    assert "LIMIT" in result.upper()

    q_count = "SELECT COUNT(*) FROM clients"
    assert mgr._guard_pagination(q_count) == q_count

    q_insert = "INSERT INTO clients (name) VALUES ('test')"
    assert mgr._guard_pagination(q_insert) == q_insert


def test_invalidate_after_write():
    mgr = DatabaseManager()
    with mock.patch("app.core.database.invalidate_cache_domains") as m:
        mgr._invalidate_after_write("INSERT INTO sales (id) VALUES (1)")
        m.assert_called_once()
        domains = set(m.call_args[0])
        assert "sales" in domains
        assert "dashboard" in domains


def test_env_int_clamping():
    mgr = DatabaseManager()
    assert mgr._env_int("FAB_NONEXISTENT_XYZ_12345", 42, 1, 100) == 42

    with mock.patch.dict("os.environ", {"FAB_CLM_MIN_TEST_XYZ": "0"}):
        assert mgr._env_int("FAB_CLM_MIN_TEST_XYZ", 5, 1, 10) == 1

    with mock.patch.dict("os.environ", {"FAB_CLM_MAX_TEST_XYZ": "999"}):
        assert mgr._env_int("FAB_CLM_MAX_TEST_XYZ", 5, 1, 10) == 10


def test_record_performance_event():
    mgr = DatabaseManager()
    mgr._record_performance_event("sql", "SELECT 1", 150.0, "details")
    assert mgr.pending_performance_event_count() >= 0


def test_is_sqlite():
    assert isinstance(is_sqlite(), bool)


@pytest.mark.asyncio
async def test_unit_of_work_lifecycle():
    fake_session = mock.AsyncMock()
    fake_session.is_active = True
    fake_session.commit = mock.AsyncMock()
    fake_session.rollback = mock.AsyncMock()
    fake_session.close = mock.AsyncMock()

    fake_session_maker = mock.MagicMock()
    fake_session_maker.return_value.__aenter__.return_value = fake_session
    fake_session_maker.return_value.__aexit__.return_value = None

    with mock.patch("app.core.uow.get_async_sessionmaker", return_value=fake_session_maker):
        async with unit_of_work() as session:
            assert session == fake_session

        fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_uow_decorator():
    fake_session = mock.AsyncMock()
    fake_session.is_active = True
    fake_session.commit = mock.AsyncMock()
    fake_session.rollback = mock.AsyncMock()

    fake_session_maker = mock.MagicMock()
    fake_session_maker.return_value.__aenter__.return_value = fake_session
    fake_session_maker.return_value.__aexit__.return_value = None

    @with_uow
    async def sample_service(x: int, db=None):
        assert db == fake_session
        return x * 10

    with mock.patch("app.core.uow.get_async_sessionmaker", return_value=fake_session_maker):
        res = await sample_service(5)
        assert res == 50
