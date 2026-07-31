"""Tests de couverture ciblés — Lot 18.

Couvre: assistant/tool_actions_production.py (add_production missing finished product & missing raw material in recipe)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.assistant.tool_actions_production import handle_production


# ── tool_actions_production.py (98% → target 100%) ─────────────────


@pytest.mark.asyncio
async def test_handle_production_add_production_finished_product_not_found():
    """add_production_batch returns error if finished_product_id is missing from DB."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    args = {"finished_product_id": 999, "quantity": 10.0}
    res = await handle_production("add_production_batch", args, session_maker)

    assert "error" in res
    assert "introuvable" in res["error"]


@pytest.mark.asyncio
async def test_handle_production_add_production_recipe_raw_material_not_found():
    """add_production_batch returns error if a raw material in the recipe is missing."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    db_product = MagicMock()
    db_recipe = MagicMock()
    db_recipe.id = 1

    recipe_item = MagicMock()
    recipe_item.raw_material_id = 888
    recipe_item.quantity = 2.0

    mock_res1 = MagicMock()
    mock_res1.scalar_one_or_none.return_value = db_product

    mock_res2 = MagicMock()
    mock_res2.scalar_one_or_none.return_value = db_recipe

    mock_res3 = MagicMock()
    mock_res3.scalars.return_value.all.return_value = [recipe_item]

    mock_res4 = MagicMock()
    mock_res4.scalar_one_or_none.return_value = None  # Raw material missing

    mock_session.execute.side_effect = [mock_res1, mock_res2, mock_res3, mock_res4]

    args = {"finished_product_id": 1, "quantity": 5.0}
    res = await handle_production("add_production_batch", args, session_maker)

    assert "error" in res
    assert "Matière première ID 888 introuvable" in res["error"]

