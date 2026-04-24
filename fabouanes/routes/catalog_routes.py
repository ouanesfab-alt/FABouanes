from __future__ import annotations

from fabouanes.fastapi_compat import flash, redirect, render_template, request, url_for

from fabouanes.core.activity import log_activity
from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.decorators import login_required
from fabouanes.core.helpers import (
    catalog_name_form_context,
    refresh_sale_profits_for_item,
    resolve_catalog_item_name,
    to_float,
    unit_choices,
)
from fabouanes.core.storage import backup_database
from fabouanes.routes.route_utils import bind_route


def register_catalog_routes(app):
    @login_required
    def catalog():
        raw_items = query_db(
            "SELECT id, name, unit AS unit, stock_qty, avg_cost, sale_price, 'Matière première' AS kind FROM raw_materials ORDER BY name"
        )
        finished_items = query_db(
            "SELECT id, name, default_unit AS unit, stock_qty, avg_cost, sale_price, 'Produit fini' AS kind FROM finished_products ORDER BY name"
        )
        all_products = sorted([dict(row) for row in raw_items] + [dict(row) for row in finished_items], key=lambda row: (row["kind"], row["name"]))
        return render_template("catalog.html", raw_items=raw_items, finished_items=finished_items, all_products=all_products)

    @login_required
    def raw_materials():
        return redirect(url_for("catalog"))

    @login_required
    def products():
        return redirect(url_for("catalog"))

    @login_required
    def quick_add():
        default_target = request.args.get("target", "client")
        options = [
            ("client", "Client", url_for("new_client")),
            ("supplier", "Fournisseur", url_for("new_supplier")),
            ("product_raw", "Matière première", url_for("new_catalog_item", kind="raw")),
            ("product_finished", "Produit fini", url_for("new_catalog_item", kind="finished")),
            ("purchase", "Achat", url_for("new_purchase")),
            ("sale", "Vente", url_for("new_sale")),
            ("production", "Production", url_for("new_production")),
            ("payment", "Versement", url_for("new_payment")),
            ("advance", "Avance", url_for("new_payment")),
        ]
        return render_template("quick_add.html", options=options, default_target=default_target)

    @login_required
    def new_catalog_item():
        kind = request.args.get("kind", "raw")
        if request.method == "POST":
            kind = request.form.get("kind", kind)
            item_name = resolve_catalog_item_name(request.form)
            if kind == "raw":
                execute_db(
                    "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item_name,
                        request.form["unit"].strip(),
                        to_float(request.form.get("stock_qty")),
                        to_float(request.form.get("avg_cost")),
                        to_float(request.form.get("sale_price")),
                        to_float(request.form.get("alert_threshold")),
                    ),
                )
                log_activity("create_product", "raw_material", None, item_name)
                backup_database("create_raw_material")
                flash("Matière première ajoutée.", "success")
            else:
                execute_db(
                    "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (?, ?, ?, ?, ?)",
                    (
                        item_name,
                        request.form["unit"].strip(),
                        to_float(request.form.get("stock_qty")),
                        to_float(request.form.get("sale_price")),
                        to_float(request.form.get("avg_cost")),
                    ),
                )
                log_activity("create_product", "finished_product", None, item_name)
                backup_database("create_finished_product")
                flash("Produit fini ajouté.", "success")
            return redirect(url_for("catalog"))
        return render_template(
            "catalog_new.html",
            kind=kind,
            units=unit_choices(),
            **catalog_name_form_context(kind),
        )

    @login_required
    def edit_raw_material(material_id: int):
        material = query_db("SELECT * FROM raw_materials WHERE id = ?", (material_id,), one=True)
        if not material:
            flash("Matière introuvable.", "danger")
            return redirect(url_for("raw_materials"))
        if request.method == "POST":
            item_name = resolve_catalog_item_name(request.form)
            avg_cost = to_float(request.form.get("avg_cost"))
            sale_price = to_float(request.form.get("sale_price"))
            execute_db(
                "UPDATE raw_materials SET name=?, unit=?, stock_qty=?, avg_cost=?, sale_price=?, alert_threshold=? WHERE id=?",
                (
                    item_name,
                    request.form["unit"].strip(),
                    to_float(request.form.get("stock_qty")),
                    avg_cost,
                    sale_price,
                    to_float(request.form.get("alert_threshold")),
                    material_id,
                ),
            )
            refresh_sale_profits_for_item("raw", material_id, avg_cost, sale_price)
            log_activity("update_price", "raw_material", material_id, f"{item_name} | achat={avg_cost} | vente={sale_price}")
            backup_database("update_raw_material")
            flash("Matière première modifiée.", "success")
            return redirect(url_for("raw_materials"))
        return render_template(
            "raw_material_edit.html",
            material=material,
            units=unit_choices(),
            **catalog_name_form_context("raw", current_name=str(material["name"] or "")),
        )

    @login_required
    def edit_product(product_id: int):
        product = query_db("SELECT * FROM finished_products WHERE id = ?", (product_id,), one=True)
        if not product:
            flash("Produit introuvable.", "danger")
            return redirect(url_for("products"))
        if request.method == "POST":
            item_name = resolve_catalog_item_name(request.form)
            avg_cost = to_float(request.form.get("avg_cost"))
            sale_price = to_float(request.form.get("sale_price"))
            execute_db(
                "UPDATE finished_products SET name=?, default_unit=?, stock_qty=?, sale_price=?, avg_cost=? WHERE id=?",
                (
                    item_name,
                    request.form["default_unit"].strip(),
                    to_float(request.form.get("stock_qty")),
                    sale_price,
                    avg_cost,
                    product_id,
                ),
            )
            refresh_sale_profits_for_item("finished", product_id, avg_cost, sale_price)
            log_activity("update_price", "finished_product", product_id, f"{item_name} | revient={avg_cost} | vente={sale_price}")
            backup_database("update_product")
            flash("Produit modifié.", "success")
            return redirect(url_for("products"))
        return render_template(
            "product_edit.html",
            product=product,
            units=unit_choices(),
            **catalog_name_form_context("finished", current_name=str(product["name"] or "")),
        )

    @login_required
    def delete_raw_material(material_id: int):
        linked = query_db(
            "SELECT 1 FROM purchases WHERE raw_material_id=? UNION SELECT 1 FROM raw_sales WHERE raw_material_id=? UNION SELECT 1 FROM production_batch_items WHERE raw_material_id=? LIMIT 1",
            (material_id, material_id, material_id),
            one=True,
        )
        if linked:
            flash("Impossible de supprimer une matière avec historique.", "danger")
        else:
            execute_db("DELETE FROM raw_materials WHERE id=?", (material_id,))
            log_activity("delete_raw_material", "raw_material", material_id, "Suppression matière")
            backup_database("delete_raw_material")
            flash("Matière première supprimée.", "success")
        return redirect(url_for("raw_materials"))

    @login_required
    def delete_product(product_id: int):
        linked = query_db(
            "SELECT 1 FROM sales WHERE finished_product_id=? UNION SELECT 1 FROM production_batches WHERE finished_product_id=? LIMIT 1",
            (product_id, product_id),
            one=True,
        )
        if linked:
            flash("Impossible de supprimer un produit avec historique.", "danger")
        else:
            execute_db("DELETE FROM finished_products WHERE id=?", (product_id,))
            log_activity("delete_product", "finished_product", product_id, "Suppression produit")
            backup_database("delete_product")
            flash("Produit fini supprimé.", "success")
        return redirect(url_for("products"))

    bind_route(app, "/catalog", "catalog", catalog, ["GET"])
    bind_route(app, "/catalog/new", "new_catalog_item", new_catalog_item, ["GET", "POST"])
    bind_route(app, "/raw-materials", "raw_materials", raw_materials, ["GET", "POST"])
    bind_route(app, "/products", "products", products, ["GET", "POST"])
    bind_route(app, "/raw-materials/<int:material_id>/edit", "edit_raw_material", edit_raw_material, ["GET", "POST"])
    bind_route(app, "/products/<int:product_id>/edit", "edit_product", edit_product, ["GET", "POST"])
    bind_route(app, "/raw-materials/<int:material_id>/delete", "delete_raw_material", delete_raw_material, ["POST"])
    bind_route(app, "/products/<int:product_id>/delete", "delete_product", delete_product, ["POST"])
    bind_route(app, "/quick-add", "quick_add", quick_add, ["GET"])
