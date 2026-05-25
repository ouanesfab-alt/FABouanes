from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response, payment_payload, payload_to_form_data, add_cache_headers
from app.repositories.payment_repository import list_payments

from app.core.db_access import query_db_async
from app.core.permissions import PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.services.payment_service import create_payment_from_form, delete_payment_by_id, edit_payment_from_form
from app.schemas.api_schemas import PaymentCreateSchema

router = APIRouter(prefix="/api/v1", tags=["payments"])

@router.get("/payments")
async def api_get_payments(request: Request):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_READ)
    rows, total = await list_payments(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        page=int(request.query_params.get("page", 1)),
        page_size=int(request.query_params.get("page_size", 50))
    )
    
    meta = {
        "page": int(request.query_params.get("page", 1)),
        "page_size": int(request.query_params.get("page_size", 50)),
        "returned": len(rows),
        "total": total
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.post("/payments", status_code=201)
async def api_create_payment(request: Request, payload: PaymentCreateSchema):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_WRITE)
    form_data = payload_to_form_data(payload.model_dump())
    try:
        payment_id, payment_type = await asyncio.to_thread(
            create_payment_from_form, form_data
        )
    except ValueError as e:
        api_error("invalid_value", str(e), 400)
        
    payment = await asyncio.to_thread(payment_payload, payment_id)
    return json_response(api_success({"payment_type": payment_type, "payment": payment}, status_code=201))

@router.get("/payments/{payment_id}")
async def api_get_payment_detail(request: Request, payment_id: int):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_READ)
    payment = await asyncio.to_thread(payment_payload, payment_id)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)
    res_data = api_success(payment)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.put("/payments/{payment_id}")
async def api_update_payment(request: Request, payment_id: int, payload: PaymentCreateSchema):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_WRITE)
    payment = await asyncio.to_thread(payment_payload, payment_id)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)
    
    form_data = payload_to_form_data(payload.model_dump())
    try:
        await asyncio.to_thread(edit_payment_from_form, payment_id, form_data)
    except ValueError as e:
        api_error("invalid_value", str(e), 400)
    
    latest = await query_db_async("SELECT id FROM payments ORDER BY id DESC", one=True)
    updated_payment = await asyncio.to_thread(payment_payload, int(latest["id"])) if latest else None
    return json_response(api_success(updated_payment))

@router.delete("/payments/{payment_id}")
async def api_delete_payment(request: Request, payment_id: int):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_DELETE)
    payment = await asyncio.to_thread(payment_payload, payment_id)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)
        
    success = await asyncio.to_thread(delete_payment_by_id, payment_id)
    if not success:
        api_error("conflict", "Suppression impossible.", 409)
    return json_response(api_success({"deleted": True}))
