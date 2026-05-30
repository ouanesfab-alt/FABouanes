from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.transactions_service import (
    transactions_context,
    update_production_notes,
)


# ---------------------------------------------------------------------------
# Helper: build a mock transaction row dict
# ---------------------------------------------------------------------------

def _make_tx_row(
    *,
    tx_type: str = "Achat",
    tx_kind: str = "purchase",
    id: int = 1,
    tx_date: str = "2026-05-30",
    partner_name: str = "Fournisseur X",
    designation: str = "Blé dur",
    quantity: float = 100.0,
    unit: str = "kg",
    unit_price: float = 50.0,
    total: float = 5000.0,
    paid: float | None = None,
    due: float | None = None,
    document_id: int | None = None,
    tx_created_at: datetime | None = None,
) -> dict:
    if tx_created_at is None:
        tx_created_at = datetime(2026, 5, 30, 14, 30, 0)
    return {
        "tx_type": tx_type,
        "tx_kind": tx_kind,
        "id": id,
        "tx_date": tx_date,
        "partner_name": partner_name,
        "designation": designation,
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "total": total,
        "paid": paid,
        "due": due,
        "document_id": document_id,
        "tx_created_at": tx_created_at,
    }


# ---------------------------------------------------------------------------
# 1. transactions_context – filter_type='all'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_filter_all() -> None:
    """With filter_type='all' the SQL should UNION ALL purchases, sales and payments."""
    mock_row = _make_tx_row()

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [
            {"c": 1},       # count query
            [mock_row],     # paginated rows
        ]

        result = await transactions_context(filter_type="all")

        # The count query (first call) must contain UNION ALL for all three sub-queries
        count_sql = mock_query.call_args_list[0][0][0]
        assert "UNION ALL" in count_sql
        # All three tables present
        assert "purchases" in count_sql
        assert "sales" in count_sql
        assert "payments" in count_sql

        assert result["filter_type"] == "all"
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["tx_time"] == "14:30"


# ---------------------------------------------------------------------------
# 2. transactions_context – filter_type='purchase'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_filter_purchase() -> None:
    """With filter_type='purchase' only the purchases sub-query should appear."""
    mock_row = _make_tx_row(tx_kind="purchase")

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 1}, [mock_row]]

        result = await transactions_context(filter_type="purchase")

        count_sql = mock_query.call_args_list[0][0][0]
        assert "purchases" in count_sql
        assert "payments" not in count_sql
        # sales sub-query uses "sales s" and "raw_sales rs"; neither should appear
        assert "raw_sales" not in count_sql

        assert result["filter_type"] == "purchase"
        assert len(result["transactions"]) == 1


# ---------------------------------------------------------------------------
# 3. transactions_context – filter_type='sale'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_filter_sale() -> None:
    """With filter_type='sale' only the sales sub-query should appear."""
    mock_row = _make_tx_row(tx_type="Vente", tx_kind="sale_finished")

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 1}, [mock_row]]

        result = await transactions_context(filter_type="sale")

        count_sql = mock_query.call_args_list[0][0][0]
        assert "sales" in count_sql
        assert "purchases" not in count_sql
        assert "payments" not in count_sql

        assert result["filter_type"] == "sale"


# ---------------------------------------------------------------------------
# 4. transactions_context – filter_type='payment'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_filter_payment() -> None:
    """With filter_type='payment' only the payments sub-query should appear."""
    mock_row = _make_tx_row(tx_type="Versement", tx_kind="payment", quantity=None, unit=None, unit_price=None)

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 1}, [mock_row]]

        result = await transactions_context(filter_type="payment")

        count_sql = mock_query.call_args_list[0][0][0]
        assert "payments" in count_sql
        assert "purchases" not in count_sql
        assert "raw_sales" not in count_sql

        assert result["filter_type"] == "payment"


# ---------------------------------------------------------------------------
# 5. transactions_context – name filter adds LIKE conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_name_filter() -> None:
    """Providing filter_name should inject LIKE %s placeholders and pass the value."""
    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 0}, []]

        await transactions_context(filter_type="purchase", filter_name="Blé")

        count_sql = mock_query.call_args_list[0][0][0]
        assert "LIKE %s" in count_sql

        # The params should contain the LIKE pattern
        count_params = mock_query.call_args_list[0][0][1]
        assert any("%blé%" in str(p) for p in count_params)


# ---------------------------------------------------------------------------
# 6. transactions_context – date filter adds date = %s condition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_date_filter() -> None:
    """Providing filter_date should inject date = %s in the WHERE clause."""
    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 0}, []]

        await transactions_context(filter_type="sale", filter_date="2026-05-30")

        count_sql = mock_query.call_args_list[0][0][0]
        assert "sale_date = %s" in count_sql

        count_params = mock_query.call_args_list[0][0][1]
        assert "2026-05-30" in count_params


# ---------------------------------------------------------------------------
# 7. update_production_notes – successful update + audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_production_notes_success() -> None:
    """Should UPDATE the batch, then log activity and audit with before/after snapshots."""
    before_row = {"id": 7, "notes": "old notes", "production_date": "2026-05-01"}
    after_row = {"id": 7, "notes": "new notes", "production_date": "2026-05-15"}

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.transactions_service.execute_db_async", new_callable=AsyncMock) as mock_exec, \
         patch("app.services.transactions_service.log_activity") as mock_log, \
         patch("app.services.transactions_service.audit_event") as mock_audit, \
         patch("app.services.transactions_service.backup_database") as mock_backup:

        # First query_db_async → SELECT before, second → SELECT after
        mock_query.side_effect = [before_row, after_row]

        await update_production_notes(batch_id=7, production_date="2026-05-15", notes="new notes")

        # Verify the UPDATE was executed
        mock_exec.assert_called_once()
        update_sql = mock_exec.call_args[0][0]
        assert "UPDATE production_batches" in update_sql

        # Verify audit received before / after
        mock_audit.assert_called_once_with(
            "edit_production_notes", "production", 7,
            before=before_row, after=after_row,
        )

        # Verify log_activity
        mock_log.assert_called_once_with(
            "edit_production_notes", "production", 7, "date=2026-05-15",
        )

        # Verify backup
        mock_backup.assert_called_once_with("edit_production_notes")


# ---------------------------------------------------------------------------
# 8. update_production_notes – missing batch_id raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_production_notes_missing_batch_id() -> None:
    """Calling with batch_id=0 (falsy) should raise ValueError immediately."""
    with pytest.raises(ValueError, match="Identifiant manquant"):
        await update_production_notes(batch_id=0, production_date="2026-05-15", notes="x")


# ---------------------------------------------------------------------------
# 9. update_production_notes – non-existent batch raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_production_notes_batch_not_found() -> None:
    """When SELECT returns None the function should raise ValueError."""
    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = None  # no row found

        with pytest.raises(ValueError, match="Production introuvable"):
            await update_production_notes(batch_id=999, production_date="", notes="x")


# ---------------------------------------------------------------------------
# 10. transactions_context – pagination (LIMIT / OFFSET in query)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_pagination() -> None:
    """Verify that LIMIT and OFFSET placeholders are used with the correct values."""
    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 100}, []]

        result = await transactions_context(
            filter_type="all",
            args={"page": "3", "page_size": "20"},
        )

        # Second call is the data query – should contain LIMIT %s OFFSET %s
        data_sql = mock_query.call_args_list[1][0][0]
        assert "LIMIT %s OFFSET %s" in data_sql

        # The last two positional params for the data query must be (page_size, offset)
        data_params = mock_query.call_args_list[1][0][1]
        # page=3, page_size=20 → offset=40
        assert data_params[-2] == 20   # page_size
        assert data_params[-1] == 40   # offset

        # Pagination metadata should reflect the numbers
        assert result["pagination"]["page"] == 3
        assert result["pagination"]["total"] == 100


# ---------------------------------------------------------------------------
# 11. transactions_context – tx_time formatting with string timestamp
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_tx_time_string_format() -> None:
    """When tx_created_at is a string (not datetime), tx_time is parsed from it."""
    mock_row = _make_tx_row(tx_created_at="2026-05-30 09:15:00")

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 1}, [mock_row]]

        result = await transactions_context(filter_type="all")

        assert result["transactions"][0]["tx_time"] == "09:15"


# ---------------------------------------------------------------------------
# 12. transactions_context – tx_time when tx_created_at is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transactions_context_tx_time_none() -> None:
    """When tx_created_at is None, tx_time should be an empty string."""
    mock_row = _make_tx_row()
    mock_row["tx_created_at"] = None

    with patch("app.services.transactions_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [{"c": 1}, [mock_row]]

        result = await transactions_context(filter_type="all")

        assert result["transactions"][0]["tx_time"] == ""
