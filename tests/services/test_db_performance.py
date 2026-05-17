from __future__ import annotations

import pytest

from app.core.db_access import get_db, query_db


def _index_names(table: str) -> set[str]:
    return {str(row["name"]) for row in query_db(f"PRAGMA index_list('{table}')")}


def test_sqlite_runtime_tuning_and_indexes():
    if getattr(get_db(), "dialect", "") != "sqlite":
        pytest.skip("SQLite-only runtime tuning check.")

    journal = query_db("PRAGMA journal_mode", one=True)
    cache_size = query_db("PRAGMA cache_size", one=True)

    assert str(journal[0]).lower() == "wal"
    assert int(cache_size[0]) <= -8192
    assert "idx_sales_client_date_id" in _index_names("sales")
    assert "idx_payments_client_date_id" in _index_names("payments")
    assert "idx_purchases_date_id" in _index_names("purchases")
