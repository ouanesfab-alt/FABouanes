from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.web.deps import get_current_user
from app.core.db_access import query_db


router = APIRouter(tags=["compat-api"])


@router.get("/api/item-info", name="api_item_info")
async def api_item_info(request: Request):
    if not get_current_user(request):
        return JSONResponse({"ok": False}, status_code=401)
    kind = str(request.query_params.get("kind", "") or "").strip()
    item_id_raw = request.query_params.get("id")
    item_id = int(item_id_raw) if str(item_id_raw or "").isdigit() else 0
    if not item_id or kind not in {"raw", "finished"}:
        return JSONResponse({"ok": False}, status_code=400)
    if kind == "raw":
        row = query_db(
            "SELECT id, name, unit, stock_qty, sale_price, avg_cost FROM raw_materials WHERE id = %s",
            (item_id,),
            one=True,
        )
        if not row:
            return JSONResponse({"ok": False}, status_code=404)
        return JSONResponse(
            {
                "ok": True,
                "item": {
                    "unit": row["unit"],
                    "stock_qty": float(row["stock_qty"]),
                    "sale_price": float(row["sale_price"]),
                    "avg_cost": float(row["avg_cost"]),
                },
            }
        )
    row = query_db(
        "SELECT id, name, default_unit AS unit, stock_qty, sale_price, avg_cost FROM finished_products WHERE id = %s",
        (item_id,),
        one=True,
    )
    if not row:
        return JSONResponse({"ok": False}, status_code=404)
    return JSONResponse(
        {
            "ok": True,
            "item": {
                "unit": row["unit"],
                "stock_qty": float(row["stock_qty"]),
                "sale_price": float(row["sale_price"]),
                "avg_cost": float(row["avg_cost"]),
            },
        }
    )


@router.get("/api/recipe/{recipe_id}", name="api_recipe")
async def api_recipe(request: Request, recipe_id: int):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    recipe = query_db(
        """
        SELECT sr.id, sr.finished_product_id, sr.name, COALESCE(sr.notes, '') AS notes, fp.name AS finished_name
        FROM saved_recipes sr
        JOIN finished_products fp ON fp.id = sr.finished_product_id
        WHERE sr.id = %s
        """,
        (recipe_id,),
        one=True,
    )
    if not recipe:
        return JSONResponse({"ok": False}, status_code=404)
    items = query_db(
        """
        SELECT sri.raw_material_id, sri.quantity, sri.position, rm.name AS material_name, rm.stock_qty, rm.unit
        FROM saved_recipe_items sri
        JOIN raw_materials rm ON rm.id = sri.raw_material_id
        WHERE sri.recipe_id = %s
        ORDER BY sri.position, sri.id
        """,
        (recipe_id,),
    )
    return JSONResponse(
        {
            "ok": True,
            "recipe": {
                "id": int(recipe["id"]),
                "finished_product_id": int(recipe["finished_product_id"]),
                "name": recipe["name"],
                "notes": recipe["notes"],
                "finished_name": recipe["finished_name"],
                "items": [
                    {
                        "raw_material_id": int(row["raw_material_id"]),
                        "quantity": float(row["quantity"]),
                        "material_name": row["material_name"],
                        "stock_qty": float(row["stock_qty"]),
                        "unit": row["unit"],
                    }
                    for row in items
                ],
            },
        }
    )
