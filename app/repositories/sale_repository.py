from __future__ import annotations

from app.core.db_access import db_task, query_db, query_db_async
from app.core.perf_cache import cached_result, invalidate_cache_domain

def _is_other_operation_item(name: str | None) -> bool:
    return str(name or "").strip().casefold() == "autre"

def invalidate_sellable_items_cache() -> None:
    invalidate_cache_domain("sales_sellable_items")
    from app.core.perf_cache import invalidate_cache_domains
    invalidate_cache_domains("dashboard", "sales", "client")

def _load_sellable_items():
    items = []
    for product in query_db("SELECT id, name, default_unit AS unit, stock_qty, sale_price, avg_cost FROM finished_products ORDER BY name"):
        items.append({
            "key": f"finished:{product['id']}",
            "label": f"{product['name']} - produit final",
            "unit": product["unit"],
            "stock_qty": product["stock_qty"],
            "sale_price": product["sale_price"],
            "avg_cost": product["avg_cost"],
            "force_unit": "",
            "custom_name_required": "",
        })
    for raw_material in query_db("""
        SELECT id, name, unit, stock_qty, sale_price, avg_cost
        FROM raw_materials
        ORDER BY CASE WHEN upper(trim(name)) = 'AUTRE' THEN 1 ELSE 0 END, name
    """):
        is_other = _is_other_operation_item(raw_material["name"])
        items.append({
            "key": f"raw:{raw_material['id']}",
            "label": f"{raw_material['name']} - {'autre produit' if is_other else 'matière première'}",
            "unit": raw_material["unit"],
            "stock_qty": raw_material["stock_qty"],
            "sale_price": raw_material["sale_price"],
            "avg_cost": raw_material["avg_cost"],
            "force_unit": "unite" if is_other else "",
            "custom_name_required": "1" if is_other else "",
        })
    return items

@db_task
def build_sellable_items():
    from app.core.perf_cache import TTL_SEMI_STABLE
    return cached_result(("sales_sellable_items",), _load_sellable_items, ttl_seconds=TTL_SEMI_STABLE)


