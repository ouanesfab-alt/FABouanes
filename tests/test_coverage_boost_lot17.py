"""Tests de couverture ciblés — Lot 17.

Couvre: assistant/tool_actions_production.py (delete_production, list_recipes, create_recipe failure, delete_recipe),
        core/helpers.py (to_float)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.assistant.tool_actions_production import handle_production


# ── tool_actions_production.py (86% → target 100%) ─────────────────


@pytest.mark.asyncio
async def test_handle_production_delete_production():
    """delete_production removes production batch by id."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.services.production_service.delete_production_by_id", new_callable=AsyncMock) as mock_del:
        res = await handle_production("delete_production", {"batch_id": 10}, session_maker)
        assert res == {"success": True, "message": "Production 10 supprimée."}
        assert mock_del.called


@pytest.mark.asyncio
async def test_handle_production_list_recipes():
    """list_recipes loads and returns saved recipes."""
    session_maker = MagicMock()

    sample_recipes = [{"id": 1, "name": "Recette Pain"}]
    with patch("app.services.recipe_service.load_saved_recipes", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = sample_recipes
        res = await handle_production("list_recipes", {}, session_maker)
        assert res == {"recipes": sample_recipes}


@pytest.mark.asyncio
async def test_handle_production_create_recipe_failure():
    """create_recipe returns error dict when save_recipe_definition returns None."""
    session_maker = MagicMock()

    with patch("app.services.recipe_service.save_recipe_definition", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = None

        args = {
            "finished_product_id": 1,
            "name": "Recette Invalide",
            "notes": "",
            "items": [{"raw_material_id": 99, "quantity": 10.0}]
        }
        res = await handle_production("create_recipe", args, session_maker)

        assert "error" in res
        assert "Impossible d'enregistrer" in res["error"]


@pytest.mark.asyncio
async def test_handle_production_delete_recipe():
    """delete_recipe deletes SavedRecipe and SavedRecipeItem records."""
    session_maker = MagicMock()
    mock_session = AsyncMock()
    session_maker.return_value.__aenter__.return_value = mock_session

    cm = MagicMock()
    cm.__aenter__ = AsyncMock()
    cm.__aexit__ = AsyncMock()
    mock_session.begin = MagicMock(return_value=cm)

    res = await handle_production("delete_recipe", {"recipe_id": 5}, session_maker)
    assert res.get("success") is True
    assert "Recette #5" in res.get("message", "")
    assert mock_session.execute.called






# ── core/helpers.py (94% → target 100%) ────────────────────────────


def test_helpers_to_float():
    """to_float converts comma and dot numbers, returning default on invalid input."""
    from app.core.helpers import to_float

    assert to_float("12,5") == 12.5
    assert to_float("100.25") == 100.25
    assert to_float(None) == 0.0
    assert to_float("invalid", default=7.5) == 7.5
