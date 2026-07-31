"""Tests unitaires pour app/core/db_helpers/execute.py et manager.py (Vague 1.4 — couverture > 90%)."""
from __future__ import annotations

from unittest import mock
import pytest
from sqlalchemy import select, column, table

from app.core.db_helpers.execute import execute_db, execute_db_async, execute_sa
from app.core.db_helpers.manager import db_manager, _clean_params


def test_execute_db_sync():
    with mock.patch.object(db_manager, "execute_db", return_value=5) as m_exec:
        res = execute_db("UPDATE test SET x=1", (1,))
        assert res == 5
        m_exec.assert_called_once_with("UPDATE test SET x=1", (1,))


@pytest.mark.asyncio
async def test_execute_db_async():
    with mock.patch.object(db_manager, "execute_db_async", return_value=10) as m_exec:
        res = await execute_db_async("DELETE FROM test", ())
        assert res == 10
        m_exec.assert_called_once_with("DELETE FROM test", ())


def test_execute_sa_compilation():
    test_table = table("users", column("id"), column("name"))
    query = test_table.update().where(test_table.c.id == 42).values(name="alice")

    with mock.patch("app.core.db_helpers.execute.execute_db", return_value=1) as m_exec:
        res = execute_sa(query)
        assert res == 1
        m_exec.assert_called_once()
        args = m_exec.call_args[0]
        assert "UPDATE users" in args[0]


def test_clean_params_various_types():
    # Float to Decimal
    assert _clean_params(1.5) == 1.5
    assert _clean_params([1.5, "test"]) == [mock.ANY, "test"]
    assert _clean_params({"key": 2.5}) == {"key": mock.ANY}
    assert _clean_params((1.5, 2.5)) == (mock.ANY, mock.ANY)
