"""Tests de couverture ciblés — Lot 11.

Couvre: db_helpers/manager.py (DatabasePoolManager helper functions & async methods)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── db_helpers/manager.py (73% → target ~85%) ──────────────────────


def test_manager_env_int_defaults_and_bounds():
    """_env_int handles default values, min/max clamps, and invalid strings."""
    from app.core.db_helpers.manager import db_manager

    # Defaults
    val = db_manager._env_int("NON_EXISTENT_VAR_XYZ", default=100, minimum=10, maximum=500)
    assert val == 100

    # Minimum clamp
    with patch.dict("os.environ", {"TEST_VAR_MIN": "2"}):
        assert db_manager._env_int("TEST_VAR_MIN", default=100, minimum=10, maximum=500) == 10

    # Maximum clamp
    with patch.dict("os.environ", {"TEST_VAR_MAX": "9999"}):
        assert db_manager._env_int("TEST_VAR_MAX", default=100, minimum=10, maximum=500) == 500

    # Invalid int string fallback to default
    with patch.dict("os.environ", {"TEST_VAR_INVALID": "not_an_int"}):
        assert db_manager._env_int("TEST_VAR_INVALID", default=42) == 42



def test_manager_sqlalchemy_database_url():
    """sqlalchemy_database_url replaces postgresql:// or postgres:// with postgresql+pg8000://."""
    from app.core.db_helpers.manager import db_manager

    url1 = "postgresql://user:pass@localhost:5432/fabouanes"
    res1 = db_manager.sqlalchemy_database_url(url1)
    assert res1.startswith("postgresql+pg8000://")

    url2 = "postgres://user:pass@localhost:5432/fabouanes"
    res2 = db_manager.sqlalchemy_database_url(url2)
    assert res2.startswith("postgresql+pg8000://")

    url3 = "sqlite:///local.db"
    res3 = db_manager.sqlalchemy_database_url(url3)
    assert res3 == "sqlite:///local.db"


def test_manager_guard_pagination():
    """_guard_pagination appends LIMIT clause to SELECT queries without existing LIMIT."""
    from app.core.db_helpers.manager import db_manager

    q1 = "SELECT * FROM clients"
    guarded1 = db_manager._guard_pagination(q1)
    assert "LIMIT" in guarded1

    q2 = "SELECT * FROM clients LIMIT 10"
    guarded2 = db_manager._guard_pagination(q2)
    assert guarded2 == q2

    q3 = "UPDATE clients SET name = 'Test'"
    guarded3 = db_manager._guard_pagination(q3)
    assert guarded3 == q3


@pytest.mark.asyncio
async def test_manager_query_db_async():
    """query_db_async wraps query_db in asyncio.to_thread."""
    from app.core.db_helpers.manager import db_manager

    with patch.object(db_manager, "query_db", return_value=[{"id": 1}]) as mock_query:
        res = await db_manager.query_db_async("SELECT 1", one=False)
        assert res == [{"id": 1}]
        assert mock_query.called


@pytest.mark.asyncio
async def test_manager_execute_db_async():
    """execute_db_async wraps execute_db in asyncio.to_thread."""
    from app.core.db_helpers.manager import db_manager

    with patch.object(db_manager, "execute_db", return_value=42) as mock_exec:
        res = await db_manager.execute_db_async("INSERT INTO clients (name) VALUES ('Async')", ())
        assert res == 42
        assert mock_exec.called


def test_manager_invalidate_after_write():
    """_invalidate_after_write invalidates appropriate cache domains for write queries."""
    from app.core.db_helpers.manager import db_manager

    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inval:
        db_manager._invalidate_after_write("INSERT INTO clients (name) VALUES ('Test')")
        assert mock_inval.called

        mock_inval.reset_mock()
        db_manager._invalidate_after_write("SELECT * FROM clients")  # Read query - no invalidation
        assert not mock_inval.called
