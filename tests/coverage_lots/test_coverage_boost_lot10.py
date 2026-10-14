"""Tests de couverture ciblés — Lot 10.

Couvre: assistant/tool_actions_operations.py, assistant/tool_actions_catalog.py,
        assistant/tool_actions_production.py, assistant/tool_actions_admin.py, assistant/tool_actions_insights.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ── tool_actions_operations.py (85% → target ~95%) ─────────────────


@pytest.mark.asyncio
async def test_handle_operations_unknown_func():
    """handle_operations returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    res = await handle_operations("unknown_action", {}, MagicMock())
    assert res is None


@pytest.mark.asyncio
async def test_handle_operations_add_sale_missing_item_id():
    """add_sale returns error when item_id / finished_product_id is missing."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    res = await handle_operations("add_sale", {"quantity": 10.0, "unit_price": 50.0}, MagicMock())
    assert "error" in res
    assert "requis" in res["error"]


@pytest.mark.asyncio
async def test_handle_operations_add_purchase_missing_item_id():
    """add_purchase returns error when raw_material_id / item_id is missing."""
    from app.modules.assistant.tool_actions_operations import handle_operations
    res = await handle_operations("add_purchase", {"quantity": 5.0, "unit_price": 100.0}, MagicMock())
    assert "error" in res
    assert "requis" in res["error"]


@pytest.mark.asyncio
async def test_handle_operations_add_payment_success():
    """add_payment creates payment via PaymentsService."""
    from app.modules.assistant.tool_actions_operations import handle_operations

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.payments.service.PaymentsService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.create_payment_from_form.return_value = (55, "REG-001")
        mock_srv_cls.return_value = mock_srv

        args = {"client_id": 1, "amount": 1000.0, "payment_type": "versement", "notes": "Acompte"}
        res = await handle_operations("add_payment", args, session_maker)

        assert res == {"success": True, "payment_id": 55}


# ── tool_actions_catalog.py (88% → target ~95%) ────────────────────


@pytest.mark.asyncio
async def test_handle_catalog_unknown_func():
    """handle_catalog returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    res = await handle_catalog("unknown_action", {}, MagicMock())
    assert res is None


@pytest.mark.asyncio
async def test_handle_catalog_add_product_finished():
    """add_product creates finished product when category is finished."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    prod_mock = MagicMock()
    prod_mock.id = 101

    with patch("app.modules.catalog.service.CatalogService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.create_finished_product.return_value = prod_mock
        mock_srv_cls.return_value = mock_srv

        args = {"name": "Pain Spécial", "category": "finished", "price": 20.0, "cost": 12.0}
        res = await handle_catalog("add_product", args, session_maker)

        assert res == {"success": True, "message": "Produit Pain Spécial ajouté.", "product_id": 101}


@pytest.mark.asyncio
async def test_handle_catalog_add_product_raw():
    """add_product creates raw material when category is raw."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    raw_mock = MagicMock()
    raw_mock.id = 202

    with patch("app.modules.catalog.service.CatalogService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.create_raw_material.return_value = raw_mock
        mock_srv_cls.return_value = mock_srv

        args = {"name": "Farine T55", "category": "raw", "price": 0.0, "cost": 45.0, "stock_qty": 100.0}
        res = await handle_catalog("add_product", args, session_maker)

        assert res == {"success": True, "message": "Produit Farine T55 ajouté.", "product_id": 202}


@pytest.mark.asyncio
async def test_handle_catalog_modify_product_not_found():
    """modify_product returns error if finished product not found."""
    from app.modules.assistant.tool_actions_catalog import handle_catalog

    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.modules.catalog.service.CatalogService") as mock_srv_cls:
        mock_srv = AsyncMock()
        mock_srv.get_product.return_value = None
        mock_srv_cls.return_value = mock_srv

        args = {"product_id": 999, "category": "finished", "name": "New Name"}
        res = await handle_catalog("modify_product", args, session_maker)

        assert "error" in res


# ── tool_actions_production.py / admin / insights handlers ─────────


@pytest.mark.asyncio
async def test_handle_production_unknown_func():
    """handle_production returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_production import handle_production
    res = await handle_production("unknown_action", {}, MagicMock())
    assert res is None


@pytest.mark.asyncio
async def test_handle_admin_unknown_func():
    """handle_admin returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_admin import handle_admin
    res = await handle_admin("unknown_action", {}, MagicMock())
    assert res is None


@pytest.mark.asyncio
async def test_handle_insights_unknown_func():
    """handle_insights returns None for unknown func_name."""
    from app.modules.assistant.tool_actions_insights import handle_insights
    res = await handle_insights("unknown_action", {}, MagicMock())
    assert res is None
