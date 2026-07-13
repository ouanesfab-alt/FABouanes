# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
from app.modules.assistant.tool_actions import sanitize_numeric

logger = logging.getLogger("fabouanes.assistant")

async def handle_production(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "add_production_batch":
            finished_product_id = int(func_args.get("finished_product_id"))
            quantity = sanitize_numeric(func_args.get("quantity"))
            notes = str(func_args.get("notes", "")).strip()
    
            from app.core.models_pkg.catalog import FinishedProduct, RawMaterial
            from app.core.models_pkg.production import ProductionBatch, ProductionBatchItem, SavedRecipe, SavedRecipeItem
            from app.services.stock_service import apply_finished_production, apply_raw_material_consumption
            from sqlmodel import select
            from decimal import Decimal
            import datetime
    
            async with session_maker() as session:
                # 1. Fetch finished product
                prod_res = await session.execute(select(FinishedProduct).where(FinishedProduct.id == finished_product_id))
                db_product = prod_res.scalar_one_or_none()
                if not db_product:
                    return {"error": f"Produit final ID {finished_product_id} introuvable."}
    
                # 2. Check for a recipe
                recipe_res = await session.execute(select(SavedRecipe).where(SavedRecipe.finished_product_id == finished_product_id))
                db_recipe = recipe_res.scalar_one_or_none()
    
                recipe_lines = []
                total_cost = 0.0
    
                if db_recipe:
                    # Fetch recipe ingredients
                    items_res = await session.execute(select(SavedRecipeItem).where(SavedRecipeItem.recipe_id == db_recipe.id))
                    recipe_items = items_res.scalars().all()
    
                    for item in recipe_items:
                        mat_res = await session.execute(select(RawMaterial).where(RawMaterial.id == item.raw_material_id))
                        material = mat_res.scalar_one_or_none()
                        if not material:
                            return {"error": f"Matière première ID {item.raw_material_id} introuvable dans la recette."}
    
                        req_qty = float(item.quantity) * quantity
                        line_cost = req_qty * float(material.avg_cost)
                        recipe_lines.append({
                            "material": material,
                            "qty": req_qty,
                            "unit_cost": float(material.avg_cost),
                            "line_cost": line_cost
                        })
                        total_cost += line_cost
    
                # 3. Create the batch
                batch = ProductionBatch(
                    finished_product_id=finished_product_id,
                    output_quantity=Decimal(str(quantity)),
                    production_cost=Decimal(str(total_cost)),
                    unit_cost=Decimal(str(total_cost / quantity if quantity > 0 else 0.0)),
                    production_date=datetime.date.today(),
                    notes=notes
                )
                session.add(batch)
                await session.flush()
                batch_id = batch.id
    
                # 4. Consume ingredients and add batch items
                for line in recipe_lines:
                    item = ProductionBatchItem(
                        batch_id=batch_id,
                        raw_material_id=line["material"].id,
                        quantity=Decimal(str(line["qty"])),
                        unit_cost_snapshot=Decimal(str(line["unit_cost"])),
                        line_cost=Decimal(str(line["line_cost"]))
                    )
                    session.add(item)
                    # Deduct from raw material stock and record movement
                    await apply_raw_material_consumption(
                        material={"id": line["material"].id},
                        qty=line["qty"],
                        reference_type="production",
                        reference_id=batch_id,
                        reason="production",
                        db=session
                    )
    
                # 5. Add finished product to stock and record movement
                await apply_finished_production(
                    product={"id": finished_product_id},
                    output_qty=quantity,
                    total_cost=total_cost,
                    reference_id=batch_id,
                    db=session
                )
    
                await session.commit()
    
            return {"success": True, "batch_id": batch_id}

    elif func_name == "delete_production":
            batch_id = int(func_args.get("batch_id"))
            from app.services.production_service import delete_production_by_id
            async with session_maker() as session:
                await delete_production_by_id(batch_id, db=session)
                await session.commit()
            return {"success": True, "message": f"Production {batch_id} supprimée."}

    elif func_name == "list_recipes":
            from app.services.recipe_service import load_saved_recipes
            recipes = await load_saved_recipes()
            return {"recipes": recipes}

    elif func_name == "create_recipe":
            from app.services.recipe_service import save_recipe_definition
            finished_id = int(func_args.get("finished_product_id") or 0)
            name = func_args.get("name", "").strip()
            notes = func_args.get("notes", "").strip()
            items = func_args.get("items", [])
            
            recipe_lines = []
            for it in items:
                raw_id = int(it.get("raw_material_id") or 0)
                qty = float(it.get("quantity") or 0.0)
                recipe_lines.append({
                    "material": {"id": raw_id},
                    "qty": qty
                })
                
            recipe_id = await save_recipe_definition(
                finished_id=finished_id,
                recipe_name=name,
                notes=notes,
                recipe_lines=recipe_lines
            )
            if recipe_id:
                return {"success": True, "recipe_id": recipe_id, "message": f"Recette '{name}' enregistrée avec succès (ID: {recipe_id})."}
            return {"error": "Impossible d'enregistrer la recette. Vérifiez les composants."}

    elif func_name == "delete_recipe":
            from sqlalchemy import delete
            from app.core.models import SavedRecipe, SavedRecipeItem
            recipe_id = int(func_args.get("recipe_id") or 0)
            async with session_maker() as session:
                async with session.begin():
                    await session.execute(delete(SavedRecipeItem).where(SavedRecipeItem.recipe_id == recipe_id))
                    await session.execute(delete(SavedRecipe).where(SavedRecipe.id == recipe_id))
            return {"success": True, "message": f"Recette #{recipe_id} supprimée avec succès."}

    return None
