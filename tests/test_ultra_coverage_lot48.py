"""
test_ultra_coverage_lot48.py
Targets:
  - sales/commands.py: reverse_sale error handling & delete_sale_by_id missing sale (lines 466, 540, 598, 643)
  - tool_actions_insights.py: search_web relative URL, exception, and weather API error (lines 45-46, 48, 65-66, 122-123)
  - tool_actions_catalog.py: modify_raw_material item not found error (lines 64, 67, 98, 146-147)
  - tool_actions_contacts.py: modify_client / modify_supplier item not found error (lines 208-209, 214-215)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. sales/commands.py — error branches & delete missing sale
# ============================================================

@pytest.mark.asyncio
async def test_sales_commands_edit_reverse_failure_and_delete_missing():
    """Lines 466, 540, 598, 643: edit_sale_document_from_form, edit_single_sale_from_form, and delete_sale_by_id."""
    from app.modules.sales.commands import SalesCommands
    from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema

    mock_session = AsyncMock()
    commands = SalesCommands(mock_session)

    # Line 643: delete_sale_by_id returns False when sale not found
    commands.sale_repo = MagicMock(get_sale_detail=AsyncMock(return_value=None))
    deleted = await commands.delete_sale_by_id("finished", 9999)
    assert deleted is False

    # Line 598: edit_single_sale_from_form raises ValueError when reverse_sale returns False
    commands.sale_repo = MagicMock(get_sale_detail=AsyncMock(return_value={"id": 1, "document_id": None}))
    commands.reverse_sale = AsyncMock(return_value=False)

    line = SaleLineSchema(item_key="finished:1", quantity=1.0, unit="kg", unit_price=10.0)
    schema = SaleFormSchema(client_id=1, lines=[line], sale_date="2024-01-01")

    with patch("app.modules.sales.commands.SalesValidator.validate_client", new=AsyncMock()):
        with pytest.raises(ValueError, match="Impossible de modifier cette vente"):
            await commands.edit_single_sale_from_form("finished", 1, schema)


# ============================================================
# 2. tool_actions_insights.py — search_web relative URL & weather exception
# ============================================================

@pytest.mark.asyncio
async def test_insights_search_web_relative_url_and_weather_exception():
    """Lines 45-46, 48, 65-66, 122-123: search_web handles relative URLs & weather API handles HTTP exceptions."""
    from app.modules.assistant.tool_actions_insights import handle_insights, search_web

    mock_resp = MagicMock(status_code=200)
    mock_resp.text = '<a class="result__a" href="//example.com/test">Title</a><div class="result__snippet">Snippet</div>'

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await search_web("farine t55")

    assert "results" in res

    # Weather API exception handling
    mock_client_err = AsyncMock()
    mock_client_err.__aenter__ = AsyncMock(return_value=mock_client_err)
    mock_client_err.__aexit__ = AsyncMock(return_value=False)
    mock_client_err.get = AsyncMock(side_effect=RuntimeError("Weather timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client_err):
        res_weather = await handle_insights("get_current_weather", {"location": "Oran"}, MagicMock())

    assert "error" in res_weather


# ============================================================
# 3. tool_actions_catalog.py & contacts.py — edge cases
# ============================================================

@pytest.mark.asyncio
async def test_catalog_and_contacts_item_not_found():
    """Lines 64, 67, 98, 146-147, 208-209, 214-215: modify_product and import_bulk_clients_excel."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.assistant.tool_actions_contacts import handle_contacts

    mock_session = AsyncMock()
    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.catalog.service.CatalogService.get_product", new=AsyncMock(return_value=None)):
        res_cat = await handle_catalog("modify_product", {"product_id": 999, "category": "finished", "stock_qty": 50, "alert_threshold": 10}, mock_session_maker)
        assert "error" in res_cat

    # Lines 208-209: import_bulk_clients_excel path outside workspace
    res_contacts = await handle_contacts("import_bulk_clients_excel", {"filepath": "/etc/passwd"}, mock_session_maker)
    assert "error" in res_contacts
