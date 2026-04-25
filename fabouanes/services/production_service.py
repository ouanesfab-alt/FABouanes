from __future__ import annotations

from datetime import date

from flask import g

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import db_transaction, execute_db, query_db
from fabouanes.core.helpers import reverse_production, save_recipe_definition, to_float
from fabouanes.core.perf_cache import cached_result
from fabouanes.core.storage import backup_database
from fabouanes.repositories.production_repository import list_production_page_context, production_form_context


def productions_context():
    return cached_result(("productions_context",), list_production_page_context, ttl_seconds=6.0)


def new_production_context():
    return production_form_context()


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
    product = query_db("SELECT * FROM finished_products WHERE id = ?", (finished_id,), one=True)
    if not product:
        raise ValueError("Produit fini introuvable.")
    recipe_lines = []
    total_cost = 0.0
    total_recipe_qty = 0.0
    for raw_id, qty_str in zip(raw_ids, quantities):
        if not raw_id:
            continue
        qty = to_float(qty_str)
        if qty <= 0:
            continue
        material = query_db("SELECT * FROM raw_materials WHERE id = ?", (int(raw_id),), one=True)
        if not material:
            raise ValueError("Une matiere premiere selectionnee est introuvable.")
        if qty > float(material["stock_qty"]):
            raise ValueError(f"Stock insuffisant pour {material['name']}.")
        line_cost = qty * float(material["avg_cost"])
        recipe_lines.append({"material": material, "qty": qty, "unit_cost": float(material["avg_cost"]), "line_cost": line_cost})
        total_cost += line_cost
        total_recipe_qty += qty
    if not recipe_lines:
        raise ValueError("Ajoute au moins une matiere premiere dans la recette.")

    recipe_id = None
    with db_transaction():
        batch_id = execute_db(
            "INSERT INTO production_batches (finished_product_id, output_quantity, production_cost, unit_cost, production_date, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (finished_id, output_qty, total_cost, (total_cost / output_qty) if output_qty else 0, production_date, notes),
        )
        for line in recipe_lines:
            execute_db(
                "INSERT INTO production_batch_items (batch_id, raw_material_id, quantity, unit_cost_snapshot, line_cost) VALUES (?, ?, ?, ?, ?)",
                (batch_id, int(line["material"]["id"]), line["qty"], line["unit_cost"], line["line_cost"]),
            )
            new_stock = float(line["material"]["stock_qty"]) - line["qty"]
            execute_db("UPDATE raw_materials SET stock_qty = ? WHERE id = ?", (new_stock, int(line["material"]["id"])))
        current_stock = float(product["stock_qty"])
        current_value = current_stock * float(product["avg_cost"])
        new_value = current_value + total_cost
        new_stock = current_stock + output_qty
        new_avg = (new_value / new_stock) if new_stock > 0 else 0
        sale_price = float(product["sale_price"]) if float(product["sale_price"]) > 0 else new_avg * 1.15
        execute_db("UPDATE finished_products SET stock_qty = ?, avg_cost = ?, sale_price = ? WHERE id = ?", (new_stock, new_avg, sale_price, finished_id))
        if save_recipe_flag:
            recipe_id = save_recipe_definition(
                finished_id,
                recipe_name or f"Recette {product['name']}",
                notes,
                recipe_lines,
                int(g.user["id"]) if getattr(g, "user", None) else None,
            )

    batch = query_db("SELECT * FROM production_batches WHERE id = ?", (batch_id,), one=True)
    log_activity("create_production", "production", batch_id, f"produit #{finished_id} sortie={output_qty}kg cout={total_cost}")
    audit_event(
        "create_production",
        "production",
        batch_id,
        after=batch,
        meta={"recipe_id": recipe_id, "lines": [{"raw_material_id": line["material"]["id"], "quantity": line["qty"]} for line in recipe_lines]},
    )
    if recipe_id:
        recipe = query_db("SELECT * FROM saved_recipes WHERE id = ?", (recipe_id,), one=True)
        audit_event("save_recipe", "recipe", recipe_id, after=recipe)
    backup_database("create_production")
    remainder = output_qty - total_recipe_qty
    return {"batch_id": batch_id, "recipe_id": recipe_id, "recipe_label": recipe_name or f"Recette {product['name']}", "remainder": remainder}


def delete_production_by_id(batch_id: int) -> bool:
    before = query_db("SELECT * FROM production_batches WHERE id = ?", (batch_id,), one=True)
    ok = reverse_production(batch_id)
    if ok:
        log_activity("delete_production", "production", batch_id, "Suppression production")
        audit_event("delete_production", "production", batch_id, before=before, after=None)
        backup_database("delete_production")
    return ok
