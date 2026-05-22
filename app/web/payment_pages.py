from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.helpers import wants_print_after_submit
from app.core.permissions import PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.core.request_state import set_state_value
from app.services.payment_service import (
    create_payment_from_form,
    delete_payment_by_id,
    edit_payment_from_form,
    get_edit_payment_context,
    new_payment_context,
)
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates


router = APIRouter()

PAYMENTS_FILTER_URL = "/operations?type=payment"
NEW_PAYMENT_URL = "/operations/payments/new"


def _new_payment_redirect_url(request: Request) -> str:
    return f"{NEW_PAYMENT_URL}?{request.url.query}" if request.url.query else NEW_PAYMENT_URL


@router.get("/payments", name="payments")
async def payments_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_READ)
    if denied:
        return denied
    return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)


@router.post("/payments", name="payments")
async def payments_submit(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    try:
        create_payment_from_form(form)
        flash(request, "Paiement enregistré.", "success")
    except Exception as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)


@router.get("/payments/new", name="compat_new_payment")
async def compat_new_payment_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(_new_payment_redirect_url(request), status_code=303)


@router.get("/operations/payments/new", name="new_payment")
async def new_payment_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    mode = request.query_params.get("mode", "versement")
    return RedirectResponse(f"/operations/new?mode={mode}", status_code=303)



@router.post("/operations/payments/new", name="new_payment")
@router.post("/payments/new", name="compat_new_payment_submit")
async def new_payment_submit(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    mode = form.get("payment_type", "versement")
    try:
        payment_id, payment_type = create_payment_from_form(form)
        flash(request, "Avance enregistrée." if payment_type == "avance" else "Versement enregistré.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/payment/{payment_id}", status_code=303)
        return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(f"{NEW_PAYMENT_URL}?mode={mode}", status_code=303)


@router.get("/payments/{payment_id}/edit", name="compat_edit_payment")
async def compat_edit_payment_page(request: Request, payment_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/operations/payments/{payment_id}/edit", status_code=303)


@router.get("/operations/payments/{payment_id}/edit", name="edit_payment")
async def edit_payment_page(request: Request, payment_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    context = get_edit_payment_context(payment_id)
    if not context:
        flash(request, "Versement introuvable.", "danger")
        return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("payment_edit.html", template_context(request, **context))


@router.post("/operations/payments/{payment_id}/edit", name="edit_payment")
@router.post("/payments/{payment_id}/edit", name="compat_edit_payment_submit")
async def edit_payment_submit(request: Request, payment_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    try:
        edit_payment_from_form(payment_id, form)
        flash(request, "Transaction client modifiée.", "success")
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)


@router.post("/operations/payments/{payment_id}/delete", name="delete_payment")
@router.post("/payments/{payment_id}/delete", name="compat_delete_payment")
async def delete_payment(request: Request, payment_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    if delete_payment_by_id(payment_id):
        flash(request, "Transaction client supprimée.", "success")
    else:
        flash(request, "Transaction introuvable.", "danger")
    return RedirectResponse(PAYMENTS_FILTER_URL, status_code=303)
