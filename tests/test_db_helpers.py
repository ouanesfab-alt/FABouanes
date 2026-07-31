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


# ---------------------------------------------------------------------------
# Tests des méthodes utilitaires de DatabaseManager — couverture C2 (lot C)
# ---------------------------------------------------------------------------

def test_sqlalchemy_url_postgresql():
    r = db_manager.sqlalchemy_database_url("postgresql://u:p@h/db")
    assert r.startswith("postgresql+pg8000://")
    assert "u:p@h/db" in r


def test_sqlalchemy_url_postgres():
    r = db_manager.sqlalchemy_database_url("postgres://u:p@h/db")
    assert r.startswith("postgresql+pg8000://")


def test_sqlalchemy_url_other_unchanged():
    r = db_manager.sqlalchemy_database_url("sqlite:///test.db")
    assert r == "sqlite:///test.db"


def test_sqlalchemy_url_empty():
    r = db_manager.sqlalchemy_database_url("")
    assert r == ""


def test_guard_pagination_adds_limit_to_bare_select():
    result = db_manager._guard_pagination("SELECT id, name FROM clients")
    assert "LIMIT" in result.upper()


def test_guard_pagination_skips_count_star():
    q = "SELECT COUNT(*) FROM clients"
    assert db_manager._guard_pagination(q) == q


def test_guard_pagination_skips_count_1():
    q = "SELECT COUNT(1) FROM orders"
    assert db_manager._guard_pagination(q) == q


def test_guard_pagination_skips_insert():
    q = "INSERT INTO clients (name) VALUES ('test')"
    assert db_manager._guard_pagination(q) == q


def test_guard_pagination_skips_update():
    q = "UPDATE clients SET name='x' WHERE id=1"
    assert db_manager._guard_pagination(q) == q


def test_guard_pagination_no_double_limit():
    q = "SELECT id FROM clients LIMIT 5"
    result = db_manager._guard_pagination(q)
    assert result.upper().count("LIMIT") == 1


def test_invalidate_after_write_sales_insert():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO sales (id) VALUES (1)")
        m.assert_called_once()
        domains = set(m.call_args[0])
        assert "sales" in domains
        assert "dashboard" in domains


def test_invalidate_after_write_clients_update():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("UPDATE clients SET name='x'")
        m.assert_called_once()
        assert "clients" in set(m.call_args[0])


def test_invalidate_after_write_skips_select():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("SELECT id FROM clients")
        m.assert_not_called()


def test_invalidate_after_write_raw_materials():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("UPDATE raw_materials SET price=100")
        assert "catalog" in set(m.call_args[0])


def test_invalidate_after_write_finished_products():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO finished_products (name) VALUES ('x')")
        assert "catalog" in set(m.call_args[0])


def test_invalidate_after_write_purchases():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO purchases (id) VALUES (1)")
        assert "purchases" in set(m.call_args[0])


def test_invalidate_after_write_production():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO production_batches (id) VALUES (1)")
        assert "productions" in set(m.call_args[0])


def test_invalidate_after_write_expenses():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO expenses (amount) VALUES (500)")
        assert "dashboard" in set(m.call_args[0])


def test_invalidate_after_write_users():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("UPDATE users SET role='admin'")
        assert "admin" in set(m.call_args[0])


def test_invalidate_after_write_audit_logs():
    with mock.patch("app.core.db_helpers.manager.invalidate_cache_domains") as m:
        db_manager._invalidate_after_write("INSERT INTO audit_logs (action) VALUES ('x')")
        assert "admin" in set(m.call_args[0])


def test_env_int_default_when_missing():
    assert db_manager._env_int("FAB_NONEXISTENT_XYZ_12345", 42, 1, 100) == 42


def test_env_int_clamps_to_min():
    with mock.patch.dict("os.environ", {"FAB_CLM_MIN_TEST_XYZ": "0"}):
        assert db_manager._env_int("FAB_CLM_MIN_TEST_XYZ", 5, 1, 10) == 1


def test_env_int_clamps_to_max():
    with mock.patch.dict("os.environ", {"FAB_CLM_MAX_TEST_XYZ": "999"}):
        assert db_manager._env_int("FAB_CLM_MAX_TEST_XYZ", 5, 1, 10) == 10


def test_env_int_valid_value():
    with mock.patch.dict("os.environ", {"FAB_CLM_VAL_TEST_XYZ": "7"}):
        assert db_manager._env_int("FAB_CLM_VAL_TEST_XYZ", 5, 1, 10) == 7


def test_env_int_invalid_string_returns_default():
    with mock.patch.dict("os.environ", {"FAB_CLM_STR_TEST_XYZ": "notanint"}):
        assert db_manager._env_int("FAB_CLM_STR_TEST_XYZ", 42, 1, 100) == 42


def test_record_sql_timing_below_threshold_no_event():
    with mock.patch.object(db_manager, "_record_performance_event") as m:
        db_manager._record_sql_timing("SELECT 1", (), 5.0)
        m.assert_not_called()


def test_record_sql_timing_above_threshold_fires_event():
    with mock.patch.object(db_manager, "_record_performance_event") as m:
        db_manager._record_sql_timing("SELECT id FROM clients", (), 99999.0)
        m.assert_called_once()
        args = m.call_args[0]
        assert args[0] == "sql"


def test_performance_event_normalizes_unknown_kind():
    with mock.patch.object(db_manager, "_ensure_performance_worker"), \
         mock.patch.object(db_manager._perf_event, "set"):
        with db_manager._perf_lock:
            before = len(db_manager._perf_queue)
        db_manager._record_performance_event("badkind", "test_op", 350.0)
        with db_manager._perf_lock:
            assert len(db_manager._perf_queue) > before
            last = db_manager._perf_queue[-1]
        assert last[0] == "route"


def test_performance_event_skips_performance_logs_table():
    with mock.patch.object(db_manager, "_ensure_performance_worker") as m_worker:
        db_manager._record_performance_event("sql", "performance_logs", 1000.0)
        m_worker.assert_not_called()


def test_performance_event_skips_zero_elapsed():
    with mock.patch.object(db_manager, "_ensure_performance_worker") as m_worker:
        db_manager._record_performance_event("sql", "some_query", 0.0)
        m_worker.assert_not_called()
