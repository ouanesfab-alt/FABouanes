import pytest
from decimal import Decimal
from unittest import mock
import asyncio

from app.core.db_helpers.manager import (
    CompatRow,
    _wrap_rows,
    _clean_params,
    CompatCursor,
    db_manager,
    postgres_pool_status,
    list_columns,
    db_task,
    db_transaction,
    get_setting,
    set_setting,
)
from app.core.db_helpers import query_db, execute_db

def test_compat_row():
    # Test dictionary-like row proxy
    row_data = {"id": 1, "name": "Test Item", "price": 10.5}
    row = CompatRow(row_data)
    
    assert row["id"] == 1
    assert row["name"] == "Test Item"
    assert row[0] == 1
    assert row[1] == "Test Item"
    assert row[2] == 10.5

def test_clean_params():
    # Convert floats to Decimals inside parameters
    params = (1.5, [2.5, "keep"], {"a": 3.5})
    cleaned = _clean_params(params)
    assert cleaned[0] == Decimal("1.5")
    assert cleaned[1][0] == Decimal("2.5")
    assert cleaned[2]["a"] == Decimal("3.5")
    
    # Test tuple param
    cleaned_tuple = _clean_params((10.25,))
    assert cleaned_tuple == (Decimal("10.25"),)

def test_wrap_rows():
    # Test row wrapping
    rows = [(1, "Alice"), (2, "Bob")]
    desc = [("id",), ("name",)]
    wrapped = _wrap_rows(rows, desc)
    assert len(wrapped) == 2
    assert wrapped[0]["name"] == "Alice"
    assert wrapped[1][0] == 2

    # None description
    assert _wrap_rows(rows, None) == rows

def test_compat_cursor():
    mock_cursor = mock.MagicMock()
    mock_cursor.description = [("id",), ("name",)]
    mock_cursor.fetchall.return_value = [(1, "Alice")]
    mock_cursor.fetchone.return_value = (2, "Bob")
    mock_cursor.lastrowid = 123

    compat = CompatCursor(mock_cursor)
    assert compat.lastrowid == 123
    
    # Fetchall
    res_all = compat.fetchall()
    assert len(res_all) == 1
    assert res_all[0]["name"] == "Alice"

    # Fetchone
    res_one = compat.fetchone()
    assert res_one["name"] == "Bob"

    compat.close()
    assert mock_cursor.close.called

    # Fetchone None
    mock_cursor.fetchone.return_value = None
    assert compat.fetchone() is None

def test_db_manager_settings():
    # Mock settings calls to avoid real DB access
    with mock.patch.object(db_manager, "query_db") as mock_query, \
         mock.patch.object(db_manager, "execute_db") as mock_execute:
        
        mock_query.return_value = {"value": "my_val_456"}
        
        set_setting("test_key_123", "my_val_456")
        mock_execute.assert_called_once()
        
        val = get_setting("test_key_123")
        assert val == "my_val_456"

def test_db_transaction_and_queries():
    # Mock connection and cursor
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
    # Mock engine and pool
    mock_pool = mock.MagicMock()
    mock_pool.size.return_value = 10
    mock_pool.checkedin.return_value = 5
    mock_pool.checkedout.return_value = 2
    mock_pool.overflow.return_value = 1
    
    mock_engine = mock.MagicMock()
    mock_engine.pool = mock_pool
    
    with mock.patch.object(db_manager, "get_database_engine", return_value=mock_engine):
        status = postgres_pool_status("sqlite:///mock")
        assert status["engine"] == "sqlite"
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

    # Sync call
    assert mock_db_operation(5) == 10
    assert mock_db_operation.sync(5) == 10

    # Async call
    res = await mock_db_operation.async_(5)
    assert res == 10


@pytest.mark.asyncio
async def test_async_query_and_execute():
    from app.core.db_helpers import query_db_async, execute_db_async
    with mock.patch.object(db_manager, "query_db", return_value={"res": 1}) as mock_q, \
         mock.patch.object(db_manager, "execute_db", return_value=42) as mock_e:

        q_res = await query_db_async("SELECT 1", one=True)
        assert q_res == {"res": 1}

        e_res = await execute_db_async("INSERT INTO dummy VALUES (1)")
        assert e_res == 42

