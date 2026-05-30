from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response, payload_to_form_data, production_payload, add_cache_headers
from app.core.db_access import query_db_async
from app.core.permissions import PERMISSION_PRODUCTION_DELETE, PERMISSION_PRODUCTION_READ, PERMISSION_PRODUCTION_WRITE
from app.services.production_service import create_production_from_form, delete_production_by_id
from app.repositories.production_repository import list_production_batches, list_recipes
from app.schemas.api_schemas import ProductionCreateSchema

router = APIRouter(prefix="/api/v1", tags=["production"])

@router.get("/production-batches")
async def api_get_production_batches(request: Request):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_READ)
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
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.post("/production-batches", status_code=201)
async def api_create_production_batch(request: Request, payload: ProductionCreateSchema):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_WRITE)
    
    # Use by_alias=True to map "raw_material_ids" to "raw_material_id[]", and "quantities" to "quantity[]"
    data_dict = payload.model_dump(by_alias=True)
    
    # In case the user passed raw_material_ids instead of raw_material_id[] in JSON, handle it:
    if "raw_material_id[]" not in data_dict or data_dict["raw_material_id[]"] is None:
        data_dict["raw_material_id[]"] = []
    if "quantity[]" not in data_dict or data_dict["quantity[]"] is None:
        data_dict["quantity[]"] = []
        
    form_data = payload_to_form_data(data_dict)
    
    try:
        result = await create_production_from_form(form_data)
    except ValueError as e:
        api_error("invalid_value", str(e), 400)
        
    batch = await production_payload(result["batch_id"])
    return json_response(api_success({"batch": batch, "recipe_id": result["recipe_id"]}, status_code=201))

@router.get("/production-batches/{batch_id}")
async def api_get_production_batch_detail(request: Request, batch_id: int):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_READ)
    batch = await production_payload(batch_id)
    if not batch:
        api_error("not_found", "Production introuvable.", 404)
    items = await query_db_async("SELECT * FROM production_batch_items WHERE batch_id = %s ORDER BY id", (batch_id,))
    payload = dict(batch)
    payload["items"] = [dict(item) for item in items]
    res_data = api_success(payload)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.delete("/production-batches/{batch_id}")
async def api_delete_production_batch(request: Request, batch_id: int):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_DELETE)
    batch = await production_payload(batch_id)
    if not batch:
        api_error("not_found", "Production introuvable.", 404)
    success = await delete_production_by_id(batch_id)
    if not success:
        api_error("conflict", "Suppression impossible.", 409)
    return json_response(api_success({"deleted": True}))

@router.get("/recipes")
async def api_recipes(request: Request):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_READ)
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_recipes(page=page, page_size=page_size)
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.get("/recipes/{recipe_id}")
async def api_recipe_detail(request: Request, recipe_id: int):
    await asyncio.to_thread(require_api_user, request, PERMISSION_PRODUCTION_READ)
    row = await query_db_async("SELECT * FROM saved_recipes WHERE id = %s", (recipe_id,), one=True)
    if not row:
        api_error("not_found", "Recette introuvable.", 404)
    items = await query_db_async("SELECT * FROM saved_recipe_items WHERE recipe_id = %s ORDER BY position, id", (recipe_id,))
    payload = dict(row)
    payload["items"] = [dict(item) for item in items]
    res_data = api_success(payload)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response
