from __future__ import annotations

from app.core.events import DomainEvent, emit
from app.utils.pagination import paginate_sequence
from app.core.connection import execute_db_async, query_db_async
from app.core.helpers import refresh_sale_profits_for_item, to_float, unit_choices
from app.repositories.client_repository import async_compat

@async_compat
async def catalog_context(args=None, path: str = "/catalog") -> dict:
    search = str((args or {}).get("q", "") or "").strip()
    kind_filter = str((args or {}).get("kind", "all") or "all").strip().lower()
    if kind_filter not in {"all", "raw", "finished"}:
        kind_filter = "all"
    from app.core.perf_cache import async_cached_result
    base = await async_cached_result(("catalog_context",), _build_catalog_context, ttl_seconds=6.0)
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


async def _build_catalog_context() -> dict:
    from datetime import date, timedelta
    cutoff_30d = (date.today() - timedelta(days=30)).isoformat()
    
    # Raw materials 30-day velocity
    raw_velocity_rows = await query_db_async(
        """
        WITH consumed AS (
            SELECT raw_material_id, SUM(qty) AS consumed_30d
            FROM (
                SELECT raw_material_id,
                       CASE
                           WHEN lower(unit) LIKE 'sac%' THEN quantity * COALESCE(NULLIF(regexp_replace(unit, '[^0-9.]', '', 'g'), ''), '50')::numeric
                           WHEN lower(unit) IN ('qt', 'quintal') THEN quantity * 100
                           ELSE quantity
                       END AS qty
                FROM raw_sales
                WHERE sale_date >= %s
                UNION ALL
                SELECT pbi.raw_material_id, pbi.quantity AS qty
                FROM production_batch_items pbi
                JOIN production_batches pb ON pb.id = pbi.batch_id
                WHERE pb.production_date >= %s
            ) source
            GROUP BY raw_material_id
        )
        SELECT rm.id, COALESCE(c.consumed_30d, 0) AS consumed_30d
        FROM raw_materials rm
        LEFT JOIN consumed c ON c.raw_material_id = rm.id
        """,
        (cutoff_30d, cutoff_30d)
    )
    raw_velocities = {r["id"]: float(r["consumed_30d"]) / 30.0 for r in raw_velocity_rows}

    # Finished products 30-day velocity
    finished_velocity_rows = await query_db_async(
        """
        WITH sold AS (
            SELECT finished_product_id, SUM(quantity) AS sold_30d
            FROM sales
            WHERE sale_date >= %s
            GROUP BY finished_product_id
        )
        SELECT fp.id, COALESCE(s.sold_30d, 0) AS sold_30d
        FROM finished_products fp
        LEFT JOIN sold s ON s.finished_product_id = fp.id
        """,
        (cutoff_30d,)
    )
    finished_velocities = {r["id"]: float(r["sold_30d"]) / 30.0 for r in finished_velocity_rows}

    raw_items = await query_db_async(
        "SELECT id, name, unit AS unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty, 'Matière première' AS kind FROM raw_materials ORDER BY name"
    )
    finished_items = await query_db_async(
        "SELECT id, name, default_unit AS unit, stock_qty, avg_cost, sale_price, 'Produit fini' AS kind FROM finished_products ORDER BY name"
    )
    all_products = []
    for row in raw_items:
        item = dict(row)
        item["row_kind"] = "raw"
        
        # Calculate days left
        v = raw_velocities.get(item["id"], 0.0)
        item["days_left"] = int(round(float(item["stock_qty"]) / v)) if v > 0.001 else None
        
        # Proactive alerts
        threshold = float(item["threshold_qty"] or item["alert_threshold"] or 0)
        is_below_threshold = float(item["stock_qty"]) <= threshold
        
        item["is_low"] = is_below_threshold or (item["days_left"] is not None and item["days_left"] <= 7)
        if item["is_low"]:
            item["autonomy_status"] = "CRITICAL"
        elif item["days_left"] is not None and item["days_left"] <= 14:
            item["autonomy_status"] = "WARNING"
        else:
            item["autonomy_status"] = "OK"
            
        all_products.append(item)
        
    for row in finished_items:
        item = dict(row)
        item["row_kind"] = "finished"
        
        # Calculate days left
        v = finished_velocities.get(item["id"], 0.0)
        item["days_left"] = int(round(float(item["stock_qty"]) / v)) if v > 0.001 else None
        
        # Proactive alerts
        item["is_low"] = item["days_left"] is not None and item["days_left"] <= 7
        if item["is_low"]:
            item["autonomy_status"] = "CRITICAL"
        elif item["days_left"] is not None and item["days_left"] <= 14:
            item["autonomy_status"] = "WARNING"
        else:
            item["autonomy_status"] = "OK"
            
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


RAW_MATERIAL_PRESETS = [
    "Maïs", 
    "Orge", 
    "Son", 
    "Soya", 
    "CMV", 
    "Phosphate",
    "Soja",
    "Son de blé",
    "Concentré",
    "Sel",
    "Carbonate",
    "Sac vide (50kg)",
    "Sac vide (25kg)"
]
FINISHED_PRODUCT_PRESETS = [
    "Aliment Démarrage",
    "Aliment Croissance",
    "Aliment Finition",
    "Aliment Pondeuse",
    "Aliment Vache Laitière",
    "Aliment Engraissement",
    "Aliment Démarrage (Sac 50kg)",
    "Aliment Croissance (Sac 50kg)",
    "Aliment Finition (Sac 50kg)",
    "Aliment Pondeuse (Sac 50kg)",
    "Aliment Vache Laitière (Sac 50kg)",
    "Aliment Engraissement (Sac 50kg)",
    "Poussin d'un jour",
    "Poussin Chair",
    "Poussin Pondeuse",
    "Oeufs (Plateau 30)"
]

def _resolve_name_from_form(form, kind: str = None) -> str:
    name = str(form.get("name", "")).strip()
    if not kind:
        kind = str(form.get("kind", "raw")).strip()
    presets = RAW_MATERIAL_PRESETS if kind == "raw" else FINISHED_PRODUCT_PRESETS
    if not name:
        return "autre"
    # If the user typed a preset name, keep it as-is
    if name in presets:
        return name
    # If the user typed something custom, check if it already has the prefix
    lower_name = name.lower()
    if lower_name.startswith("autre:"):
        return name
    elif lower_name.startswith("autre :"):
        return f"autre: {name[7:].strip()}"
    else:
        return f"autre: {name}"


def new_catalog_context(kind: str = "raw") -> dict:
    return {
        "kind": "finished" if kind == "finished" else "raw",
        "units": unit_choices(),
        "raw_presets": RAW_MATERIAL_PRESETS,
        "finished_presets": FINISHED_PRODUCT_PRESETS,
        "other_category_value": "__other__",
        "custom_name_value": ""
    }


@async_compat
async def create_catalog_item_from_form(form) -> tuple[str, int]:
    kind = str(form.get("kind", "raw")).strip()
    name = _resolve_name_from_form(form, kind)
    if kind == "raw":
        item_id = await execute_db_async(
            "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                name,
                str(form["unit"]).strip(),
                to_float(form.get("stock_qty")),
                to_float(form.get("avg_cost")),
                to_float(form.get("sale_price")),
                to_float(form.get("alert_threshold")),
            ),
        )
        created = await get_raw_material(item_id)
        emit(DomainEvent("create", "raw_material", item_id, name, after=created))
        return "raw", item_id
    item_id = await execute_db_async(
        "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (%s, %s, %s, %s, %s)",
        (
            name,
            str(form["unit"]).strip(),
            to_float(form.get("stock_qty")),
            to_float(form.get("sale_price")),
            to_float(form.get("avg_cost")),
        ),
    )
    created = await get_product(item_id)
    emit(DomainEvent("create", "finished_product", item_id, name, after=created))
    return "finished", item_id


@async_compat
async def get_raw_material(material_id: int):
    return await query_db_async("SELECT * FROM raw_materials WHERE id = %s", (material_id,), one=True)


@async_compat
async def get_product(product_id: int):
    return await query_db_async("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)


@async_compat
async def raw_material_edit_context(material_id: int) -> dict | None:
    material = await get_raw_material(material_id)
    if not material:
        return None
    name = material["name"]
    is_preset = name in RAW_MATERIAL_PRESETS
    if is_preset:
        custom_val = name
    else:
        lower_name = name.lower()
        if lower_name.startswith("autre:"):
            custom_val = name[6:].strip()
        elif lower_name.startswith("autre :"):
            custom_val = name[7:].strip()
        else:
            custom_val = name
    return {
        "material": material,
        "units": unit_choices(),
        "name_presets": RAW_MATERIAL_PRESETS,
        "custom_name_value": custom_val
    }


@async_compat
async def product_edit_context(product_id: int) -> dict | None:
    product = await get_product(product_id)
    if not product:
        return None
    name = product["name"]
    is_preset = name in FINISHED_PRODUCT_PRESETS
    if is_preset:
        custom_val = name
    else:
        lower_name = name.lower()
        if lower_name.startswith("autre:"):
            custom_val = name[6:].strip()
        elif lower_name.startswith("autre :"):
            custom_val = name[7:].strip()
        else:
            custom_val = name
    return {
        "product": product,
        "units": unit_choices(),
        "name_presets": FINISHED_PRODUCT_PRESETS,
        "custom_name_value": custom_val
    }


@async_compat
async def update_raw_material_from_form(material_id: int, form) -> None:
    before = await get_raw_material(material_id)
    avg_cost = to_float(form.get("avg_cost"))
    sale_price = to_float(form.get("sale_price"))
    name = _resolve_name_from_form(form)
    await execute_db_async(
        "UPDATE raw_materials SET name = %s, unit = %s, stock_qty = %s, avg_cost = %s, sale_price = %s, alert_threshold = %s WHERE id = %s",
        (
            name,
            str(form["unit"]).strip(),
            to_float(form.get("stock_qty")),
            avg_cost,
            sale_price,
            to_float(form.get("alert_threshold")),
            material_id,
        ),
    )
    refresh_sale_profits_for_item("raw", material_id, avg_cost, sale_price)
    updated = await get_raw_material(material_id)
    emit(DomainEvent("update", "raw_material", material_id, f"{name} | achat={avg_cost} | vente={sale_price}", before=before, after=updated))


@async_compat
async def update_product_from_form(product_id: int, form) -> None:
    before = await get_product(product_id)
    avg_cost = to_float(form.get("avg_cost"))
    sale_price = to_float(form.get("sale_price"))
    name = _resolve_name_from_form(form)
    await execute_db_async(
        "UPDATE finished_products SET name = %s, default_unit = %s, stock_qty = %s, sale_price = %s, avg_cost = %s WHERE id = %s",
        (
            name,
            str(form["default_unit"]).strip(),
            to_float(form.get("stock_qty")),
            sale_price,
            avg_cost,
            product_id,
        ),
    )
    refresh_sale_profits_for_item("finished", product_id, avg_cost, sale_price)
    updated = await get_product(product_id)
    emit(DomainEvent("update", "finished_product", product_id, f"{name} | revient={avg_cost} | vente={sale_price}", before=before, after=updated))


@async_compat
async def delete_raw_material_by_id(material_id: int) -> bool:
    linked = await query_db_async(
        "SELECT 1 FROM purchases WHERE raw_material_id = %s UNION SELECT 1 FROM raw_sales WHERE raw_material_id = %s UNION SELECT 1 FROM production_batch_items WHERE raw_material_id = %s LIMIT 1",
        (material_id, material_id, material_id),
        one=True,
    )
    if linked:
        return False
    before = await get_raw_material(material_id)
    await execute_db_async("DELETE FROM raw_materials WHERE id = %s", (material_id,))
    emit(DomainEvent("delete", "raw_material", material_id, "Suppression matière", before=before))
    return True


@async_compat
async def delete_product_by_id(product_id: int) -> bool:
    linked = await query_db_async(
        "SELECT 1 FROM sales WHERE finished_product_id = %s UNION SELECT 1 FROM production_batches WHERE finished_product_id = %s LIMIT 1",
        (product_id, product_id),
        one=True,
    )
    if linked:
        return False
    before = await get_product(product_id)
    await execute_db_async("DELETE FROM finished_products WHERE id = %s", (product_id,))
    emit(DomainEvent("delete", "finished_product", product_id, "Suppression produit", before=before))
    return True

