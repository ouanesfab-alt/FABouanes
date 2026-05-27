from __future__ import annotations

from datetime import date

from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import db_transaction, execute_db, query_db
from app.core.helpers import to_float
from app.core.perf_cache import cached_result
from app.core.storage import mark_backup_needed
from app.repositories.production_repository import list_production_page_context, production_form_context
from app.repositories.sale_repository import invalidate_sellable_items_cache
from app.services.recipe_service import save_recipe_definition
from app.services.stock_service import apply_finished_production, apply_raw_material_consumption
from app.services.stock_service import reverse_production
from app.core.request_state import get_state_value


def productions_context(args=None):
    args = args or {}
    cache_key = tuple(sorted((str(key), str(value)) for key, value in dict(args).items()))
    return cached_result(("productions_context", cache_key), lambda: list_production_page_context(args), ttl_seconds=30.0)


def new_production_context():
    return production_form_context()


def _current_user_id() -> int | None:
    user = get_state_value("user")
    if user:
        try:
            return int(user["id"])
        except Exception:
            return None
    return None




def create_production_from_form(form):
    finished_id = int(form["finished_product_id"])
    output_qty = to_float(form.get("output_quantity"))
    production_date = form.get("production_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    recipe_name = (form.get("recipe_name") or "").strip()
    save_recipe_flag = (form.get("save_recipe") or "1").strip() not in ("0", "false", "off")
    raw_ids = form.getlist("raw_material_id[]")
    quantities = form.getlist("quantity[]")
    if production_date > date.today().isoformat():
        raise ValueError("La date de production ne peut pas etre dans le futur.")
    if output_qty <= 0:
        raise ValueError("La quantite produite doit etre superieure a zero.")
    product = query_db("SELECT * FROM finished_products WHERE id = %s", (finished_id,), one=True)
    if not product:
        raise ValueError("Produit final introuvable.")
    recipe_lines = []
    total_cost = 0.0
    total_recipe_qty = 0.0
    for raw_id, qty_str in zip(raw_ids, quantities):
        if not raw_id:
            continue
        qty = to_float(qty_str)
        if qty <= 0:
            continue
        material = query_db("SELECT * FROM raw_materials WHERE id = %s", (int(raw_id),), one=True)
        if not material:
            raise ValueError("Une matière première selectionnee est introuvable.")
        if qty > float(material["stock_qty"]):
            raise ValueError(f"Stock insuffisant pour {material['name']}.")
        line_cost = qty * float(material["avg_cost"])
        recipe_lines.append({"material": material, "qty": qty, "unit_cost": float(material["avg_cost"]), "line_cost": line_cost})
        total_cost += line_cost
        total_recipe_qty += qty
    if not recipe_lines:
        raise ValueError("Ajoute au moins une matière première dans la recette.")

    recipe_id = None
    with db_transaction():
        batch_id = execute_db(
            "INSERT INTO production_batches (finished_product_id, output_quantity, production_cost, unit_cost, production_date, notes) VALUES (%s, %s, %s, %s, %s, %s)",
            (finished_id, output_qty, total_cost, (total_cost / output_qty) if output_qty else 0, production_date, notes),
        )
        for line in recipe_lines:
            execute_db(
                "INSERT INTO production_batch_items (batch_id, raw_material_id, quantity, unit_cost_snapshot, line_cost) VALUES (%s, %s, %s, %s, %s)",
                (batch_id, int(line["material"]["id"]), line["qty"], line["unit_cost"], line["line_cost"]),
            )
            apply_raw_material_consumption(line["material"], line["qty"], "production", batch_id, "create_production")
        apply_finished_production(product, output_qty, total_cost, batch_id)
        if save_recipe_flag:
            recipe_id = save_recipe_definition(
                finished_id,
                recipe_name or f"Recette {product['name']}",
                notes,
                recipe_lines,
                _current_user_id(),
            )

    batch = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
    log_activity("create_production", "production", batch_id, f"produit #{finished_id} sortie={output_qty}kg cout={total_cost}")
    audit_event(
        "create_production",
        "production",
        batch_id,
        after=batch,
        meta={"recipe_id": recipe_id, "lines": [{"raw_material_id": line["material"]["id"], "quantity": line["qty"]} for line in recipe_lines]},
    )
    if recipe_id:
        recipe = query_db("SELECT * FROM saved_recipes WHERE id = %s", (recipe_id,), one=True)
        audit_event("save_recipe", "recipe", recipe_id, after=recipe)
    invalidate_sellable_items_cache()
    mark_backup_needed("create_production")
    remainder = output_qty - total_recipe_qty
    return {"batch_id": batch_id, "recipe_id": recipe_id, "recipe_label": recipe_name or f"Recette {product['name']}", "remainder": remainder}


def delete_production_by_id(batch_id: int) -> bool:
    before = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
    ok = reverse_production(batch_id)
    if ok:
        log_activity("delete_production", "production", batch_id, "Suppression production")
        audit_event("delete_production", "production", batch_id, before=before, after=None)
        invalidate_sellable_items_cache()
        mark_backup_needed("delete_production")
    return ok
