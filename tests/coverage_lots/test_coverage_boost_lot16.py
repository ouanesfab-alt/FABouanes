"""Tests de couverture ciblés — Lot 16.

Couvre: modules/sales/queries.py (get_sale_document_context, get_sale_edit_context),
        assistant/tool_actions_admin.py (modify_app_file old content missing)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.assistant.tool_actions_admin import handle_admin


# ── sales/queries.py (83% → target 100%) ────────────────────────────


@pytest.mark.asyncio
async def test_get_sale_document_context_success():
    """get_sale_document_context returns formatted dictionary for valid document."""
    from app.modules.sales.queries import SalesQueries

    session = AsyncMock()

    doc_mock = MagicMock()
    doc_mock.client_id = 5
    doc_mock.model_dump.return_value = {"id": 10, "client_id": 5, "total": 100.0}

    lines = [{"row_kind": "finished", "row_id": 1, "quantity": 2.0}]

    with patch("app.modules.sales.repository.SaleDocumentRepository.get_by_id", new_callable=AsyncMock) as mock_get, \
         patch("app.modules.sales.repository.SaleDocumentRepository.list_lines", new_callable=AsyncMock) as mock_lines, \
         patch("app.modules.sales.repository.SaleDocumentRepository.document_has_linked_payments", new_callable=AsyncMock) as mock_linked:

        mock_get.return_value = doc_mock
        mock_lines.return_value = lines
        mock_linked.return_value = False

        queries = SalesQueries(session)
        ctx = await queries.get_sale_document_context(10)

        assert ctx is not None
        assert ctx["has_linked_payments"] is False
        assert ctx["sale_lines"] == lines


@pytest.mark.asyncio
async def test_get_sale_edit_context_redirect_document():
    """get_sale_edit_context redirects to document context if sale belongs to a document."""
    from app.modules.sales.queries import SalesQueries

    session = AsyncMock()

    sale_detail = {
        "id": 1,
        "row_kind": "finished",
        "document_id": 10,
    }

    doc_context = {
        "sale_document": {"id": 10},
        "sale_lines": [],
        "has_linked_payments": False,
    }

    with patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_sale, \
         patch("app.modules.sales.queries.SalesQueries.get_sale_document_context", new_callable=AsyncMock) as mock_doc_ctx:

        mock_sale.return_value = sale_detail
        mock_doc_ctx.return_value = doc_context

        queries = SalesQueries(session)
        ctx = await queries.get_sale_edit_context("finished", 1)

        assert ctx is not None
        assert ctx["redirect_document_id"] == 10


@pytest.mark.asyncio
async def test_get_sale_edit_context_single_line():
    """get_sale_edit_context returns single sale edit schema if not in a document."""
    from app.modules.sales.queries import SalesQueries

    session = AsyncMock()

    sale_detail = {
        "id": 1,
        "client_id": 5,
        "sale_type": "credit",
        "sale_date": "2026-01-01",
        "notes": "Test note",
        "row_kind": "finished",
        "item_key": "finished:1",
        "item_name": "Pain",
        "custom_item_name": "",
        "quantity": 10.0,
        "unit": "kg",
        "unit_price": 20.0,
        "total": 200.0,
        "amount_paid": 0.0,
        "balance_due": 200.0,
        "document_id": None,
    }


    with patch("app.modules.sales.repository.SaleRepository.get_sale_detail", new_callable=AsyncMock) as mock_sale:
        mock_sale.return_value = sale_detail

        queries = SalesQueries(session)
        ctx = await queries.get_sale_edit_context("finished", 1)

        assert ctx is not None
        assert ctx["sale_document"]["id"] is None
        assert len(ctx["sale_lines"]) == 1
        assert ctx["sale_lines"][0]["item_name"] == "Pain"


# ── tool_actions_admin.py (95% → target 100%) ───────────────────────


@pytest.mark.asyncio
async def test_handle_admin_modify_app_file_old_content_not_found(tmp_path):
    """modify_app_file returns error if old_content is missing from target file."""
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello World", encoding="utf-8")

    session_maker = MagicMock()

    with patch("app.modules.assistant.tool_actions_admin._assert_workspace_path"):
        args = {
            "filepath": str(test_file),
            "old_content": "NonExistentString123",
            "new_content": "Replacement",
        }
        res = await handle_admin("modify_app_file", args, session_maker)

        assert "error" in res
        assert "n'a pas été trouvé" in res["error"]
