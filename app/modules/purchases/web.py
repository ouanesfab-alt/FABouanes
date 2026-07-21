from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.core.exceptions import get_friendly_error_message
from app.modules.purchases.service import PurchaseService
from app.modules.purchases.schemas_validation import PurchaseFormSchema
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.permissions import PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE, PERMISSION_OPERATIONS_DELETE
from app.core.helpers import wants_print_after_submit
from app.core.request_state import set_state_value

router = APIRouter(tags=["purchases"])

PURCHASES_FILTER_URL = "/operations?type=purchase"
NEW_PURCHASE_URL = "/operations/purchases/new"


@router.get("/purchases", name="purchases")
async def purchases_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_READ)
    if denied:
        return denied
    return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)


@router.post("/purchases", name="purchases")
async def purchases_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = PurchaseService(db)
    try:
        schema = PurchaseFormSchema.model_validate(form)
        created = await service.create_purchase_from_form(schema)
        flash(request, "Achat enregistré avec succès.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/{created['print_doc_type']}/{created['print_item_id']}", status_code=303)
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
    return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)


@router.get("/purchases/new", name="compat_new_purchase")
async def compat_new_purchase_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_PURCHASE_URL, status_code=303)


@router.get("/operations/purchases/new", name="new_purchase")
async def new_purchase_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse("/operations/new?mode=achat", status_code=303)


@router.post("/operations/purchases/new", name="new_purchase")
@router.post("/purchases/new", name="compat_new_purchase_submit")
async def new_purchase_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = PurchaseService(db)
    try:
        schema = PurchaseFormSchema.model_validate(form)
        created = await service.create_purchase_from_form(schema)
        flash(request, "Achat enregistré avec succès.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/{created['print_doc_type']}/{created['print_item_id']}", status_code=303)
        return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(NEW_PURCHASE_URL, status_code=303)


@router.get("/purchases/document/{document_id}/edit", name="compat_edit_purchase_document")
async def compat_edit_purchase_document_page(request: Request, document_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/operations/purchases/document/{document_id}/edit", status_code=303)


@router.get("/operations/purchases/document/{document_id}/edit", name="edit_purchase_document")
async def edit_purchase_document_page(
    request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied

    service = PurchaseService(db)
    context = await service.get_purchase_document_context(document_id)
    if not context:
        flash(request, "Bon d'achat introuvable.", "danger")
        return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)

    form_context = await service.purchase_form_context()
    form_context.update(context)
    return templates.TemplateResponse("purchase_edit.html", template_context(request, **form_context))


@router.post("/operations/purchases/document/{document_id}/edit", name="edit_purchase_document")
@router.post("/purchases/document/{document_id}/edit", name="compat_edit_purchase_document_submit")
async def edit_purchase_document_submit(
    request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = PurchaseService(db)
    try:
        schema = PurchaseFormSchema.model_validate(form)
        await service.edit_purchase_document_from_form(document_id, schema)
        flash(request, "Bon d'achat modifié.", "success")
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)


@router.get("/purchases/{purchase_id}/edit", name="compat_edit_purchase")
async def compat_edit_purchase_page(request: Request, purchase_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/operations/purchases/{purchase_id}/edit", status_code=303)


@router.get("/operations/purchases/{purchase_id}/edit", name="edit_purchase")
async def edit_purchase_page(
    request: Request, purchase_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied

    service = PurchaseService(db)
    context = await service.get_purchase_edit_context(purchase_id)
    if not context:
        flash(request, "Achat introuvable.", "danger")
        return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)
    if context.get("redirect_document_id"):
        return RedirectResponse(f"/operations/purchases/document/{context['redirect_document_id']}/edit", status_code=303)

    form_context = await service.purchase_form_context()
    form_context.update(context)
    return templates.TemplateResponse("purchase_edit.html", template_context(request, **form_context))


@router.post("/operations/purchases/{purchase_id}/edit", name="edit_purchase")
@router.post("/purchases/{purchase_id}/edit", name="compat_edit_purchase_submit")
async def edit_purchase_submit(
    request: Request, purchase_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = PurchaseService(db)
    try:
        schema = PurchaseFormSchema.model_validate(form)
        await service.edit_purchase_from_form(purchase_id, schema)
        flash(request, "Achat modifié.", "success")
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)


@router.post("/operations/purchases/{purchase_id}/delete", name="delete_purchase")
@router.post("/purchases/{purchase_id}/delete", name="compat_delete_purchase")
async def delete_purchase(
    request: Request, purchase_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)

    service = PurchaseService(db)
    if await service.delete_purchase_by_id(purchase_id):
        flash(request, "Achat supprimé et stock corrigé.", "success")
    else:
        flash(request, "Impossible de supprimer cet achat.", "danger")
    return RedirectResponse(PURCHASES_FILTER_URL, status_code=303)
