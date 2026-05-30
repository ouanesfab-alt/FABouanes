from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.services.recipe_service import load_saved_recipes, save_recipe_definition


@pytest.mark.asyncio
async def test_load_saved_recipes_empty() -> None:
    """If no recipes are in the DB, it should return an empty list."""
    with patch("app.services.recipe_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        
        result = await load_saved_recipes()
        
        assert result == []
        mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_load_saved_recipes_with_items() -> None:
    """Should correctly group raw material items and assign them to matching recipes."""
    recipe_rows = [
        {"id": 1, "finished_product_id": 10, "name": "Recipe A", "notes": "notes A", "finished_name": "Product A"},
        {"id": 2, "finished_product_id": 11, "name": "Recipe B", "notes": "", "finished_name": "Product B"}
    ]
    item_rows = [
        {"recipe_id": 1, "raw_material_id": 101, "quantity": 5.0, "position": 1, "material_name": "Mat X", "stock_qty": 50.0, "unit": "kg"},
        {"recipe_id": 1, "raw_material_id": 102, "quantity": 10.0, "position": 2, "material_name": "Mat Y", "stock_qty": 100.0, "unit": "kg"},
        {"recipe_id": 2, "raw_material_id": 101, "quantity": 2.0, "position": 1, "material_name": "Mat X", "stock_qty": 50.0, "unit": "kg"}
    ]
    
    with patch("app.services.recipe_service.query_db_async", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [recipe_rows, item_rows]
        
        result = await load_saved_recipes()
        
        assert len(result) == 2
        
        # Check Recipe A
        recipe_a = result[0]
        assert recipe_a["id"] == 1
        assert len(recipe_a["items"]) == 2
        assert recipe_a["items"][0]["raw_material_id"] == 101
        assert recipe_a["items"][0]["quantity"] == 5.0
        assert recipe_a["items"][1]["raw_material_id"] == 102
        assert recipe_a["items"][1]["quantity"] == 10.0
        
        # Check Recipe B
        recipe_b = result[1]
        assert recipe_b["id"] == 2
        assert len(recipe_b["items"]) == 1
        assert recipe_b["items"][0]["raw_material_id"] == 101
        assert recipe_b["items"][0]["quantity"] == 2.0


@pytest.mark.asyncio
async def test_save_recipe_definition_validation() -> None:
    """Empty names or lines should return None immediately."""
    res1 = await save_recipe_definition(finished_id=1, recipe_name="", notes="", recipe_lines=[{"material": {"id": 101}, "qty": 5.0}])
    res2 = await save_recipe_definition(finished_id=1, recipe_name="Recipe A", notes="", recipe_lines=[])
    assert res1 is None
    assert res2 is None


@pytest.mark.asyncio
async def test_save_recipe_definition_new() -> None:
    """Saving a new recipe should insert it and its lines."""
    recipe_lines = [
        {"material": {"id": 101}, "qty": 5.0},
        {"material": {"id": 102}, "qty": 8.5}
    ]
    
    with patch("app.services.recipe_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.recipe_service.execute_db_async", new_callable=AsyncMock) as mock_execute:
        
        # Recipe does not exist
        mock_query.return_value = None
        # Insert recipe returns ID 42
        mock_execute.return_value = 42
        
        recipe_id = await save_recipe_definition(
            finished_id=10,
            recipe_name="New Recipe",
            notes="Some notes",
            recipe_lines=recipe_lines,
            user_id=7
        )
        
        assert recipe_id == 42
        # Verify saved_recipes check
        mock_query.assert_called_once_with(
            "SELECT id FROM saved_recipes WHERE finished_product_id = %s AND lower(name) = lower(%s)",
            (10, "New Recipe"),
            one=True
        )
        # Verify inserts
        mock_execute.assert_any_call(
            "INSERT INTO saved_recipes (finished_product_id, name, notes, created_by_user_id) VALUES (%s, %s, %s, %s)",
            (10, "New Recipe", "Some notes", 7)
        )
        mock_execute.assert_any_call(
            "INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity, position) VALUES (%s, %s, %s, %s)",
            (42, 101, 5.0, 1)
        )
        mock_execute.assert_any_call(
            "INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity, position) VALUES (%s, %s, %s, %s)",
            (42, 102, 8.5, 2)
        )


@pytest.mark.asyncio
async def test_save_recipe_definition_existing() -> None:
    """Saving an existing recipe should update notes and recreate lines."""
    recipe_lines = [
        {"material": {"id": 101}, "qty": 4.0}
    ]
    
    with patch("app.services.recipe_service.query_db_async", new_callable=AsyncMock) as mock_query, \
         patch("app.services.recipe_service.execute_db_async", new_callable=AsyncMock) as mock_execute:
        
        # Recipe exists with ID 15
        mock_query.return_value = {"id": 15}
        
        recipe_id = await save_recipe_definition(
            finished_id=10,
            recipe_name="Existing Recipe",
            notes="Updated notes",
            recipe_lines=recipe_lines,
            user_id=7
        )
        
        assert recipe_id == 15
        # Verify update and delete items
        mock_execute.assert_any_call(
            "UPDATE saved_recipes SET notes = %s, updated_at = CURRENT_TIMESTAMP, created_by_user_id = COALESCE(created_by_user_id, %s) WHERE id = %s",
            ("Updated notes", 7, 15)
        )
        mock_execute.assert_any_call(
            "DELETE FROM saved_recipe_items WHERE recipe_id = %s",
            (15,)
        )
        # Verify new item insert
        mock_execute.assert_any_call(
            "INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity, position) VALUES (%s, %s, %s, %s)",
            (15, 101, 4.0, 1)
        )
