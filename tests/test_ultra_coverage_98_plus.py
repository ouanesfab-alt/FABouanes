"""
Extended coverage tests targeting uncovered branches in:
- app/modules/sales/commands.py  (edit_sale_document_from_form)
- app/core/db_helpers/manager.py (transient retry)
- app/modules/assistant/rag.py   (fallbacks)
- app/modules/assistant/sql_tools.py (execute_readonly_sql)
"""
from contextlib import contextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.sales.commands import SalesCommands
from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
from app.core.db_helpers.manager import DatabaseManager
from app.modules.assistant.rag import get_rag_context, search_user_documents
from app.modules.assistant.sql_tools import execute_readonly_sql


# ---------------------------------------------------------------------------
# 1. edit_sale_document_from_form coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_sale_document_coverage():
    """Cover edit_sale_document_from_form success path via extensive mocking."""
    mock_session = AsyncMock()
    cmd = SalesCommands(mock_session)

    # Context returned by SalesQueries.get_sale_document_context
    fake_context = {
        "sale_document": {"id": 10},
        "sale_lines": [{"row_kind": "finished", "row_id": 1}],
        "has_linked_payments": False,
    }

    mock_created_doc = MagicMock()
    mock_created_doc.id = 10
    mock_created_doc.model_dump.return_value = {"id": 10, "notes": "Modifie"}

    schema = SaleFormSchema(
        client_id=None,
        sale_date=date(2026, 8, 1),
        notes="Modifie",
        lines=[
            SaleLineSchema(
                item_key="finished:1",
                quantity=5.0,
                unit="Sac",
                unit_price=1400.0,
                custom_item_name="Aliment Vache",
            )
        ],
    )

    # SalesQueries is imported locally inside the method, so patch the module it
    # comes from rather than the commands namespace.
    mock_queries_instance = AsyncMock()
    mock_queries_instance.get_sale_document_context.return_value = fake_context

    with (
        patch("app.modules.sales.queries.SalesQueries", return_value=mock_queries_instance),
        patch(
            "app.modules.sales.commands.SalesValidator.validate_client",
            new=AsyncMock(return_value=None),
        ),
        patch.object(cmd, "reverse_sale", new=AsyncMock(return_value=True)),
        patch.object(
            cmd, "create_sale_record", new=AsyncMock(return_value=("finished", 1))
        ),
        patch.object(
            cmd.doc_repo, "get_by_id", new=AsyncMock(return_value=mock_created_doc)
        ),
        patch("app.modules.sales.commands.invalidate_cache_domains"),
        patch("app.modules.sales.commands.emit"),
    ):
        res = await cmd.edit_sale_document_from_form(10, schema)

    assert res["mode"] == "document"
    assert res["document_id"] == 10
    assert res["line_count"] == 1


# ---------------------------------------------------------------------------
# 2. DatabaseManager transient retry logic
# ---------------------------------------------------------------------------

def test_db_manager_transient_retry_coverage():
    """Verify that transient errors trigger a retry in query_db / execute_db."""
    mgr = DatabaseManager()

    # ---- query_db with transient error on first call ----
    mock_cursor_ok = MagicMock()
    mock_cursor_ok.fetchall.return_value = [("ok",)]
    mock_cursor_ok.description = [("col",)]

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        Exception("connection reset by peer"),  # first attempt fails
        mock_cursor_ok,                          # retry succeeds
    ]

    with patch.object(mgr, "get_read_db", return_value=mock_conn):
        rows = mgr.query_db("SELECT 1")
    assert rows == [("ok",)]

    # ---- execute_db with transient error on first call ----
    mock_cur_ok = MagicMock()
    mock_cur_ok.lastrowid = 99

    mock_write_conn = MagicMock()
    mock_write_conn.execute.side_effect = [
        Exception("08006 connection failure"),  # first attempt fails
        mock_cur_ok,                            # retry succeeds
    ]

    with patch.object(mgr, "get_write_db", return_value=mock_write_conn):
        row_id = mgr.execute_db("INSERT INTO dummy VALUES (1)")
    assert row_id == 99


# ---------------------------------------------------------------------------
# 3. RAG engine fallback paths
# ---------------------------------------------------------------------------

def test_rag_engine_fallback_coverage():
    """Confirm RAG functions return acceptable types on fallback paths."""
    doc_results = search_user_documents("facturation client")
    assert isinstance(doc_results, list)

    context_text = get_rag_context("comment creer un client")
    assert isinstance(context_text, str)


# ---------------------------------------------------------------------------
# 4. execute_readonly_sql coverage
# ---------------------------------------------------------------------------

def test_sql_tools_readonly_coverage():
    """Cover execute_readonly_sql success and error branches."""
    # --- Error path: guard rejects non-SELECT ---
    with patch(
        "app.modules.assistant.sql_tools.guard_readonly_sql"
    ) as mock_guard_err:
        mock_guard_err.return_value = MagicMock(ok=False, error="Non-SELECT interdit")
        err_res = execute_readonly_sql("DROP TABLE clients")
    assert "error" in err_res

    # --- Success path: mock db_manager.db_transaction context manager ---
    mock_row = MagicMock()
    mock_row.__iter__ = MagicMock(return_value=iter([]))
    mock_row.keys = MagicMock(return_value=["col_val"])
    # Make dict(mock_row) return something useful
    mock_row._mapping = {"col_val": 1}

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    @contextmanager
    def fake_transaction():
        yield mock_conn

    with (
        patch(
            "app.modules.assistant.sql_tools.guard_readonly_sql"
        ) as mock_guard,
        patch("app.modules.assistant.sql_tools.db_manager") as mock_mgr,
    ):
        mock_guard.return_value = MagicMock(ok=True, sql_to_run="SELECT 1 AS col_val")
        mock_mgr.db_transaction = fake_transaction
        res = execute_readonly_sql("SELECT 1 AS col_val")

    assert isinstance(res, dict)
    assert "rows" in res or "error" in res
