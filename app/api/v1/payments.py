from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response, payment_payload, payload_to_form_data, add_cache_headers
from app.core.async_db import get_async_session
from app.core.models import Payment
from app.core.permissions import PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.services.payment_service import create_payment_from_form, delete_payment_by_id, edit_payment_from_form
from app.core.schema.api_validation import PaymentCreateSchema

router = APIRouter(prefix="/api/v1", tags=["payments"])

@router.get("/payments")
async def api_get_payments(request: Request, db: AsyncSession = Depends(get_async_session)):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    from app.modules.payments.repository import PaymentRepository
    repo = PaymentRepository(db)
    rows, total = await repo.list_payments_paginated(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        page=page,
        page_size=page_size
    )

    meta = {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.post("/payments", status_code=201)
async def api_create_payment(request: Request, payload: PaymentCreateSchema, db: AsyncSession = Depends(get_async_session)):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_WRITE)
    form_data = payload_to_form_data(payload.model_dump())
    try:
        payment_id, payment_type = await create_payment_from_form(form_data, db=db)
    except ValueError as e:
        api_error("invalid_value", str(e), 400)

    payment = await payment_payload(payment_id, db=db)
    return json_response(api_success({"payment_type": payment_type, "payment": payment}, status_code=201))

@router.get("/payments/{payment_id}")
async def api_get_payment_detail(request: Request, payment_id: int, db: AsyncSession = Depends(get_async_session)):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_READ)
    payment = await payment_payload(payment_id, db=db)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)
    res_data = api_success(payment)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

@router.put("/payments/{payment_id}")
async def api_update_payment(request: Request, payment_id: int, payload: PaymentCreateSchema, db: AsyncSession = Depends(get_async_session)):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_WRITE)
    payment = await payment_payload(payment_id, db=db)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)

    form_data = payload_to_form_data(payload.model_dump())
    try:
        await edit_payment_from_form(payment_id, form_data, db=db)
    except ValueError as e:
        api_error("invalid_value", str(e), 400)

    stmt = select(Payment.id).order_by(Payment.id.desc()).limit(1)
    res = await db.execute(stmt)
    latest_id = res.scalar()
    updated_payment = await payment_payload(latest_id, db=db) if latest_id else None
    return json_response(api_success(updated_payment))

@router.delete("/payments/{payment_id}")
async def api_delete_payment(request: Request, payment_id: int, db: AsyncSession = Depends(get_async_session)):
    await asyncio.to_thread(require_api_user, request, PERMISSION_OPERATIONS_DELETE)
    payment = await payment_payload(payment_id, db=db)
    if not payment:
        api_error("not_found", "Paiement introuvable.", 404)

    success = await delete_payment_by_id(payment_id, db=db)
    if not success:
        api_error("conflict", "Suppression impossible.", 409)
    return json_response(api_success({"deleted": True}))
