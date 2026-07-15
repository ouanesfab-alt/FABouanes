from __future__ import annotations

from datetime import date
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.helpers import to_float
from app.core.storage import mark_backup_needed
from app.modules.sales.infrastructure.repository import invalidate_sellable_items_cache
from app.services.recipe_service import save_recipe_definition
from app.services.stock_service import apply_finished_production, apply_raw_material_consumption, reverse_production
from app.core.request_state import get_state_value
from app.core.models import FinishedProduct, RawMaterial, ProductionBatch, ProductionBatchItem, SavedRecipe


class ProductionCommands:
    """Gestion des commandes (Commands / écritures) du module Production."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _current_user_id(self) -> int | None:
        user = get_state_value("user")
        if user:
            try:
                return int(user["id"])
            except Exception:
                return None
        return None

    async def create_production_from_form(self, form: Any) -> dict:
        # Check if form has dict-like interface (FastAPI form)
        # Note: form can have .getlist()
        finished_id = int(form["finished_product_id"])
        output_qty = to_float(form.get("output_quantity"))

        production_date_val = form.get("production_date")
        if production_date_val is None:
            production_date_obj = date.today()
        elif isinstance(production_date_val, date):
            production_date_obj = production_date_val
        else:
            production_date_obj = date.fromisoformat(str(production_date_val))

        notes = form.get("notes", "").strip()
        recipe_name = (form.get("recipe_name") or "").strip()
        save_recipe_flag = (form.get("save_recipe") or "1").strip() not in ("0", "false", "off")
        
        # Support both form list and normal dictionary items for API schemas
        if hasattr(form, "getlist"):
            raw_ids = form.getlist("raw_material_id[]")
            quantities = form.getlist("quantity[]")
            valid_inputs = []
            for raw_id, qty_str in zip(raw_ids, quantities):
                if not raw_id:
                    continue
                qty = to_float(qty_str)
                if qty <= 0:
                    continue
                valid_inputs.append((int(raw_id), qty))
        else:
            # Assume structured dict (API Sync style)
            items = form.get("items") or []
            valid_inputs = []
            for item in items:
                raw_id = item.get("raw_material_id")
                qty = to_float(item.get("quantity"))
                if not raw_id or qty <= 0:
                    continue
                valid_inputs.append((int(raw_id), qty))

        if production_date_obj > date.today():
            raise ValueError("La date de production ne peut pas etre dans le futur.")
        if output_qty <= 0:
            raise ValueError("La quantite produite doit etre superieure a zero.")

        product_res = await self.session.execute(select(FinishedProduct).where(FinishedProduct.id == finished_id))
        product_obj = product_res.scalar_one_or_none()
        if not product_obj:
            raise ValueError("Produit final introuvable.")
        product = product_obj.model_dump()

        recipe_lines = []
        total_cost = 0.0
        total_recipe_qty = 0.0

        if valid_inputs:
            ids_to_query = [x[0] for x in valid_inputs]
            materials_res = await self.session.execute(select(RawMaterial).where(RawMaterial.id.in_(ids_to_query)))
            materials_rows = [m.model_dump() for m in materials_res.scalars().all()]
            materials_map = {m["id"]: m for m in materials_rows}

            for raw_id, qty in valid_inputs:
                material = materials_map.get(raw_id)
                if not material:
                    raise ValueError("Une matière première selectionnee est introuvable.")
                if qty > float(material["stock_qty"]):
                    raise ValueError(f"Stock insuffisant pour {material['name']}.")
                line_cost = qty * float(material["avg_cost"])
                recipe_lines.append({
                    "material": material,
                    "qty": qty,
                    "unit_cost": float(material["avg_cost"]),
                    "line_cost": line_cost
                })
                total_cost += line_cost
                total_recipe_qty += qty

        if not recipe_lines:
            raise ValueError("Ajoute au moins une matière première dans la recette.")

        recipe_id = None

        batch = ProductionBatch(
            finished_product_id=finished_id,
            output_quantity=output_qty,
            production_cost=total_cost,
            unit_cost=(total_cost / output_qty) if output_qty else 0,
            production_date=production_date_obj,
            notes=notes
        )
        self.session.add(batch)
        await self.session.flush()
        batch_id = batch.id

        for line in recipe_lines:
            item = ProductionBatchItem(
                batch_id=batch_id,
                raw_material_id=int(line["material"]["id"]),
                quantity=line["qty"],
                unit_cost_snapshot=line["unit_cost"],
                line_cost=line["line_cost"]
            )
            self.session.add(item)
            await apply_raw_material_consumption(
                line["material"],
                line["qty"],
                "production",
                batch_id,
                "create_production",
                db=self.session
            )

        await apply_finished_production(product, output_qty, total_cost, batch_id, db=self.session)

        if save_recipe_flag:
            recipe_id = await save_recipe_definition(
                finished_id,
                recipe_name or f"Recette {product['name']}",
                notes,
                recipe_lines,
                self._current_user_id(),
                db=self.session
            )

        batch_res = await self.session.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
        batch_obj = batch_res.scalar_one_or_none()
        batch_dict = batch_obj.model_dump() if batch_obj else None

        log_activity("create_production", "production", batch_id, f"produit #{finished_id} sortie={output_qty}kg cout={total_cost}")
        audit_event(
            "create_production",
            "production",
            batch_id,
            after=batch_dict,
            meta={"recipe_id": recipe_id, "lines": [{"raw_material_id": line["material"]["id"], "quantity": line["qty"]} for line in recipe_lines]},
        )
        if recipe_id:
            recipe_res = await self.session.execute(select(SavedRecipe).where(SavedRecipe.id == recipe_id))
            recipe_obj = recipe_res.scalar_one_or_none()
            recipe_dict = recipe_obj.model_dump() if recipe_obj else None
            audit_event("save_recipe", "recipe", recipe_id, after=recipe_dict)

        invalidate_sellable_items_cache()
        mark_backup_needed("create_production")
        remainder = output_qty - total_recipe_qty
        return {
            "batch_id": batch_id,
            "recipe_id": recipe_id,
            "recipe_label": recipe_name or f"Recette {product['name']}",
            "remainder": remainder
        }

    async def delete_production_by_id(self, batch_id: int) -> bool:
        batch_res = await self.session.execute(select(ProductionBatch).where(ProductionBatch.id == batch_id))
        batch_obj = batch_res.scalar_one_or_none()
        batch_dict = batch_obj.model_dump() if batch_obj else None

        ok = await reverse_production(batch_id, db=self.session)
        if ok:
            log_activity("delete_production", "production", batch_id, "Suppression production")
            audit_event("delete_production", "production", batch_id, before=batch_dict, after=None)
            invalidate_sellable_items_cache()
            mark_backup_needed("delete_production")
        return ok
