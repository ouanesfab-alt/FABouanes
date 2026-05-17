from __future__ import annotations

from app.core.events import DomainEvent, emit
from app.core.perf_cache import cached_result
from app.utils.pagination import paginate_sequence
from app.core.db_access import execute_db, query_db
from app.core.helpers import refresh_sale_profits_for_item, to_float, unit_choices


def catalog_context(args=None, path: str = "/catalog") -> dict:
    search = str((args or {}).get("q", "") or "").strip()
    kind_filter = str((args or {}).get("kind", "all") or "all").strip().lower()
    if kind_filter not in {"all", "raw", "finished"}:
        kind_filter = "all"
    base = cached_result(("catalog_context",), _build_catalog_context, ttl_seconds=6.0)
    products = list(base["all_products"])
    if kind_filter == "raw":
        products = [row for row in products if row.get("row_kind") == "raw"]
    elif kind_filter == "finished":
        products = [row for row in products if row.get("row_kind") == "finished"]
    if search:
        needle = search.lower()
        products = [row for row in products if needle in f"{row['name']} {row['unit']} {row['kind']}".lower()]
    page_products, pagination = paginate_sequence(products, args or {}, path)
    return {
        "raw_items": [row for row in page_products if row.get("row_kind") == "raw"],
        "finished_items": [row for row in page_products if row.get("row_kind") == "finished"],
        "all_products": page_products,
        "catalog_filters": {"q": search, "kind": kind_filter},
        "pagination": pagination,
    }


def _build_catalog_context() -> dict:
    raw_items = query_db(
        "SELECT id, name, unit AS unit, stock_qty, avg_cost, sale_price, 'Matière première' AS kind FROM raw_materials ORDER BY name"
    )
    finished_items = query_db(
        "SELECT id, name, default_unit AS unit, stock_qty, avg_cost, sale_price, 'Produit fini' AS kind FROM finished_products ORDER BY name"
    )
    all_products = []
    for row in raw_items:
        item = dict(row)
        item["row_kind"] = "raw"
        all_products.append(item)
    for row in finished_items:
        item = dict(row)
        item["row_kind"] = "finished"
        all_products.append(item)
    all_products = sorted(all_products, key=lambda row: (row["kind"], row["name"]))
    return {
        "raw_items": raw_items,
        "finished_items": finished_items,
        "all_products": all_products,
    }


def quick_add_context(default_target: str = "client") -> dict:
    return {
        "default_target": default_target,
        "options": [
            ("client", "Client", "/contacts/clients/new"),
            ("supplier", "Fournisseur", "/contacts/suppliers/new"),
            ("product_raw", "Matière première", "/catalog/new?kind=raw"),
            ("product_finished", "Produit fini", "/catalog/new?kind=finished"),
            ("purchase", "Achat", "/operations/purchases/new"),
            ("sale", "Vente", "/operations/sales/new"),
            ("production", "Production", "/production/new"),
            ("payment", "Versement", "/operations/payments/new"),
            ("advance", "Avance", "/operations/payments/new?mode=avance"),
        ],
    }


def new_catalog_context(kind: str) -> dict:
    return {"kind": "finished" if kind == "finished" else "raw", "units": unit_choices()}


def create_catalog_item_from_form(form) -> tuple[str, int]:
    kind = str(form.get("kind", "raw")).strip()
    if kind == "raw":
        item_id = execute_db(
            "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(form["name"]).strip(),
                str(form["unit"]).strip(),
                to_float(form.get("stock_qty")),
                to_float(form.get("avg_cost")),
                to_float(form.get("sale_price")),
                to_float(form.get("alert_threshold")),
            ),
        )
        created = get_raw_material(item_id)
        emit(DomainEvent("create", "raw_material", item_id, str(form["name"]).strip(), after=created))
        return "raw", item_id
    item_id = execute_db(
        "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (?, ?, ?, ?, ?)",
        (
            str(form["name"]).strip(),
            str(form["unit"]).strip(),
            to_float(form.get("stock_qty")),
            to_float(form.get("sale_price")),
            to_float(form.get("avg_cost")),
        ),
    )
    created = get_product(item_id)
    emit(DomainEvent("create", "finished_product", item_id, str(form["name"]).strip(), after=created))
    return "finished", item_id


def get_raw_material(material_id: int):
    return query_db("SELECT * FROM raw_materials WHERE id = ?", (material_id,), one=True)


def get_product(product_id: int):
    return query_db("SELECT * FROM finished_products WHERE id = ?", (product_id,), one=True)


def raw_material_edit_context(material_id: int) -> dict | None:
    material = get_raw_material(material_id)
    if not material:
        return None
    return {"material": material, "units": unit_choices()}


def product_edit_context(product_id: int) -> dict | None:
    product = get_product(product_id)
    if not product:
        return None
    return {"product": product, "units": unit_choices()}


def update_raw_material_from_form(material_id: int, form) -> None:
    before = get_raw_material(material_id)
    avg_cost = to_float(form.get("avg_cost"))
    sale_price = to_float(form.get("sale_price"))
    execute_db(
        "UPDATE raw_materials SET name = ?, unit = ?, stock_qty = ?, avg_cost = ?, sale_price = ?, alert_threshold = ? WHERE id = ?",
        (
            str(form["name"]).strip(),
            str(form["unit"]).strip(),
            to_float(form.get("stock_qty")),
            avg_cost,
            sale_price,
            to_float(form.get("alert_threshold")),
            material_id,
        ),
    )
    refresh_sale_profits_for_item("raw", material_id, avg_cost, sale_price)
    updated = get_raw_material(material_id)
    emit(DomainEvent("update", "raw_material", material_id, f"{form['name'].strip()} | achat={avg_cost} | vente={sale_price}", before=before, after=updated))


def update_product_from_form(product_id: int, form) -> None:
    before = get_product(product_id)
    avg_cost = to_float(form.get("avg_cost"))
    sale_price = to_float(form.get("sale_price"))
    execute_db(
        "UPDATE finished_products SET name = ?, default_unit = ?, stock_qty = ?, sale_price = ?, avg_cost = ? WHERE id = ?",
        (
            str(form["name"]).strip(),
            str(form["default_unit"]).strip(),
            to_float(form.get("stock_qty")),
            sale_price,
            avg_cost,
            product_id,
        ),
    )
    refresh_sale_profits_for_item("finished", product_id, avg_cost, sale_price)
    updated = get_product(product_id)
    emit(DomainEvent("update", "finished_product", product_id, f"{form['name'].strip()} | revient={avg_cost} | vente={sale_price}", before=before, after=updated))


def delete_raw_material_by_id(material_id: int) -> bool:
    linked = query_db(
        "SELECT 1 FROM purchases WHERE raw_material_id = ? UNION SELECT 1 FROM raw_sales WHERE raw_material_id = ? UNION SELECT 1 FROM production_batch_items WHERE raw_material_id = ? LIMIT 1",
        (material_id, material_id, material_id),
        one=True,
    )
    if linked:
        return False
    before = get_raw_material(material_id)
    execute_db("DELETE FROM raw_materials WHERE id = ?", (material_id,))
    emit(DomainEvent("delete", "raw_material", material_id, "Suppression matière", before=before))
    return True


def delete_product_by_id(product_id: int) -> bool:
    linked = query_db(
        "SELECT 1 FROM sales WHERE finished_product_id = ? UNION SELECT 1 FROM production_batches WHERE finished_product_id = ? LIMIT 1",
        (product_id, product_id),
        one=True,
    )
    if linked:
        return False
    before = get_product(product_id)
    execute_db("DELETE FROM finished_products WHERE id = ?", (product_id,))
    emit(DomainEvent("delete", "finished_product", product_id, "Suppression produit", before=before))
    return True
