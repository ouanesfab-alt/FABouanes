from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from app.core.events import DomainEvent, emit
from app.core.uow import register_post_commit_hook, unit_of_work
from app.infra.perf_cache import (
    cached_result,
    clear_cache,
    invalidate_cache_tags,
)
from app.modules.admin.backup_service import backup_sqlite_hot


@pytest.mark.asyncio
async def test_post_commit_hook_runs_only_after_commit():
    executed = []

    def my_hook():
        executed.append("committed")

    # In a successful unit of work
    mock_session = MagicMock()
    async def mock_commit():
        return None
    mock_session.commit.side_effect = mock_commit

    with patch("app.core.uow.get_async_sessionmaker", return_value=lambda: mock_session):
        async with unit_of_work() as session:
            register_post_commit_hook(my_hook)
            assert executed == []  # Not executed before commit

    assert executed == ["committed"]


@pytest.mark.asyncio
async def test_post_commit_hook_not_executed_on_rollback():
    executed = []

    def my_hook():
        executed.append("committed")

    mock_session = MagicMock()
    async def mock_rollback():
        return None
    mock_session.rollback.side_effect = mock_rollback

    with patch("app.core.uow.get_async_sessionmaker", return_value=lambda: mock_session):
        with pytest.raises(ValueError):
            async with unit_of_work() as session:
                register_post_commit_hook(my_hook)
                raise ValueError("Simulated business error")

    assert executed == []  # Never executed on failure


def test_tagged_cache_surgical_invalidation():
    clear_cache()

    calls_sales = 0
    calls_stock = 0

    def get_sales():
        nonlocal calls_sales
        calls_sales += 1
        return "sales_data"

    def get_stock():
        nonlocal calls_stock
        calls_stock += 1
        return "stock_data"

    # Cache items with domain tags
    val1 = cached_result(("test", "sales"), get_sales, tags=("sales", "dashboard"))
    val2 = cached_result(("test", "stock"), get_stock, tags=("stock", "dashboard"))

    assert val1 == "sales_data"
    assert val2 == "stock_data"
    assert calls_sales == 1
    assert calls_stock == 1

    # Second read from cache
    assert cached_result(("test", "sales"), get_sales, tags=("sales", "dashboard")) == "sales_data"
    assert calls_sales == 1

    # Invalidate ONLY sales
    invalidate_cache_tags("sales")

    # Stock is still cached
    assert cached_result(("test", "stock"), get_stock, tags=("stock", "dashboard")) == "stock_data"
    assert calls_stock == 1

    # Sales must re-compute
    assert cached_result(("test", "sales"), get_sales, tags=("sales", "dashboard")) == "sales_data"
    assert calls_sales == 2


def test_domain_event_triggers_cache_invalidation():
    clear_cache()
    calls = 0

    def get_kpis():
        nonlocal calls
        calls += 1
        return {"total": 100}

    # Cache with dashboard tag
    cached_result(("dashboard", "kpis"), get_kpis, tags=("dashboard", "sales"))
    assert calls == 1

    # Emit a sale creation event
    emit(DomainEvent("create", "sale", 1, "Vente comptoir"))

    # Cache must be invalidated for dashboard and sales
    cached_result(("dashboard", "kpis"), get_kpis, tags=("dashboard", "sales"))
    assert calls == 2


def test_sqlite_hot_backup_with_integrity_check(tmp_path):
    # 1. Create a valid test SQLite DB
    src_db = tmp_path / "source.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO products (name) VALUES ('Savon'), ('Shampoing')")
    conn.commit()
    conn.close()

    # 2. Run hot backup
    target_gz = tmp_path / "backups" / "backup.db.gz"
    res_path = backup_sqlite_hot(src_db, target_gz, compress=True)

    assert res_path.exists()
    assert res_path.stat().st_size > 0

    # 3. Test integrity check failure handling on corrupted DB
    corrupt_db = tmp_path / "corrupted.db"
    # Write garbage into a file pretending to be sqlite
    with open(corrupt_db, "wb") as f:
        f.write(b"NOT A SQLITE FILE")

    with pytest.raises(Exception):
        backup_sqlite_hot(corrupt_db, tmp_path / "bad_backup.db.gz")
