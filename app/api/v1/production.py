from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response, payload_to_form_data, production_payload
from app.core.db_access import query_db
from app.core.permissions import PERMISSION_PRODUCTION_DELETE, PERMISSION_PRODUCTION_READ, PERMISSION_PRODUCTION_WRITE
from app.services.production_service import create_production_from_form, delete_production_by_id
from app.repositories.production_repository import list_production_batches, list_recipes


router = APIRouter(prefix="/api/v1", tags=["production"])


@router.api_route("/production-batches", methods=["GET", "POST"])
async def api_production_batches(request: Request):
    require_api_user(request, PERMISSION_PRODUCTION_WRITE if request.method == "POST" else PERMISSION_PRODUCTION_READ)
    if request.method == "POST":
        payload = await request.json()
        result = create_production_from_form(
            payload_to_form_data(
                {
                    "finished_product_id": payload.get("finished_product_id"),
                    "output_quantity": payload.get("output_quantity"),
                    "production_date": payload.get("production_date"),
                    "notes": payload.get("notes", ""),
                    "recipe_name": payload.get("recipe_name", ""),
                    "save_recipe": payload.get("save_recipe", 0),
                    "raw_material_id[]": payload.get("raw_material_id[]", payload.get("raw_material_ids", [])),
                    "quantity[]": payload.get("quantity[]", payload.get("quantities", [])),
                }
            )
        )
        return json_response(api_success({"batch": production_payload(result["batch_id"]), "recipe_id": result["recipe_id"]}, status_code=201))

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_production_batches(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))


@router.api_route("/production-batches/{batch_id}", methods=["GET", "DELETE"])
async def api_production_batch_detail(request: Request, batch_id: int):
    require_api_user(request, PERMISSION_PRODUCTION_DELETE if request.method == "DELETE" else PERMISSION_PRODUCTION_READ)
    batch = production_payload(batch_id)
    if not batch:
        api_error("not_found", "Production introuvable.", 404)
    if request.method == "DELETE":
        if not delete_production_by_id(batch_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    items = query_db("SELECT * FROM production_batch_items WHERE batch_id = %s ORDER BY id", (batch_id,))
    payload = dict(batch)
    payload["items"] = [dict(item) for item in items]
    return json_response(api_success(payload))


@router.get("/recipes")
async def api_recipes(request: Request):
    require_api_user(request, PERMISSION_PRODUCTION_READ)
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_recipes(page=page, page_size=page_size)
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))


@router.get("/recipes/{recipe_id}")
async def api_recipe_detail(request: Request, recipe_id: int):
    require_api_user(request, PERMISSION_PRODUCTION_READ)
    row = query_db("SELECT * FROM saved_recipes WHERE id = %s", (recipe_id,), one=True)
    if not row:
        api_error("not_found", "Recette introuvable.", 404)
    items = query_db("SELECT * FROM saved_recipe_items WHERE recipe_id = %s ORDER BY position, id", (recipe_id,))
    payload = dict(row)
    payload["items"] = [dict(item) for item in items]
    return json_response(api_success(payload))
