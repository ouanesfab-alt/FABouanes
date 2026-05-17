from __future__ import annotations

import pytest

from app.core.db_access import get_db, query_db


def _index_names(table: str) -> set[str]:
    rows = query_db("SELECT indexname FROM pg_indexes WHERE tablename = %s", (table,))
    return {str(row["indexname"]) for row in rows}


def test_postgresql_performance_indexes():
    # Since we are migrating fully to PostgreSQL, let's verify that the critical performance indexes are present
    assert "idx_sales_client_date_id" in _index_names("sales")
    assert "idx_payments_client_date_id" in _index_names("payments")
    assert "idx_purchases_date_id" in _index_names("purchases")

