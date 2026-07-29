from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.core.exceptions import get_friendly_error_message
from app.core.models import Client
from app.modules.sales.service import SalesService
from app.modules.sales.schemas_validation import SaleFormSchema
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.permissions import PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE, PERMISSION_OPERATIONS_DELETE
from app.core.helpers import wants_print_after_submit
from app.core.request_state import set_state_value

router = APIRouter(tags=["sales"])

SALES_FILTER_URL = "/operations?type=sale"
NEW_SALE_URL = "/operations/sales/new"


@router.get("/sales", name="sales")
async def sales_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_READ)
    if denied:
        return denied
    return RedirectResponse(SALES_FILTER_URL, status_code=303)


@router.post("/sales", name="sales")
async def sales_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = SalesService(db)
    try:
        schema = SaleFormSchema.model_validate(form)
        created = await service.create_sale_from_form(schema)
        flash(request, "Vente enregistrée avec bénéfice estimé.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/{created['print_doc_type']}/{created['print_item_id']}", status_code=303)
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
    return RedirectResponse(SALES_FILTER_URL, status_code=303)


@router.get("/sales/new", name="compat_new_sale")
async def compat_new_sale_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_SALE_URL, status_code=303)


@router.get("/operations/sales/new", name="new_sale")
async def new_sale_page(request: Request):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse("/operations/new?mode=vente", status_code=303)


@router.post("/operations/sales/new", name="new_sale")
@router.post("/sales/new", name="compat_new_sale_submit")
async def new_sale_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = SalesService(db)
    try:
        schema = SaleFormSchema.model_validate(form)
        created = await service.create_sale_from_form(schema)
        flash(request, "Vente enregistrée avec bénéfice estimé.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/{created['print_doc_type']}/{created['print_item_id']}", status_code=303)
        return RedirectResponse(SALES_FILTER_URL, status_code=303)
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(NEW_SALE_URL, status_code=303)


@router.get("/sales/document/{document_id}/edit", name="compat_edit_sale_document")
async def compat_edit_sale_document_page(request: Request, document_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/operations/sales/document/{document_id}/edit", status_code=303)


@router.get("/operations/sales/document/{document_id}/edit", name="edit_sale_document")
async def edit_sale_document_page(
    request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied

    service = SalesService(db)
    context = await service.get_sale_document_context(document_id)
    if not context:
        flash(request, "Facture introuvable.", "danger")
        return RedirectResponse(SALES_FILTER_URL, status_code=303)

    form_context = await service.sale_form_context()
    form_context.update(context)

    # Fetch clients list for dropdown
    stmt = select(Client).order_by(Client.name)
    res = await db.execute(stmt)
    form_context["clients"] = [dict(c._mapping) for c in res.fetchall()]

    return templates.TemplateResponse("sale_edit.html", template_context(request, **form_context))


@router.post("/operations/sales/document/{document_id}/edit", name="edit_sale_document")
@router.post("/sales/document/{document_id}/edit", name="compat_edit_sale_document_submit")
async def edit_sale_document_submit(
    request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = SalesService(db)
    try:
        schema = SaleFormSchema.model_validate(form)
        await service.edit_sale_document_from_form(document_id, schema)
        flash(request, "Facture modifiée.", "success")
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(SALES_FILTER_URL, status_code=303)


@router.get("/sales/{kind}/{row_id}/edit", name="compat_edit_sale")
async def compat_edit_sale_page(request: Request, kind: str, row_id: int):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/operations/sales/{kind}/{row_id}/edit", status_code=303)


@router.get("/operations/sales/{kind}/{row_id}/edit", name="edit_sale")
async def edit_sale_page(
    request: Request, kind: str, row_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied

    service = SalesService(db)
    context = await service.get_sale_edit_context(kind, row_id)
    if not context:
        flash(request, "Vente introuvable.", "danger")
        return RedirectResponse(SALES_FILTER_URL, status_code=303)
    if context.get("redirect_document_id"):
        return RedirectResponse(f"/operations/sales/document/{context['redirect_document_id']}/edit", status_code=303)

    form_context = await service.sale_form_context()
    form_context.update(context)

    # Fetch clients
    stmt = select(Client).order_by(Client.name)
    res = await db.execute(stmt)
    form_context["clients"] = [dict(c._mapping) for c in res.fetchall()]

    return templates.TemplateResponse("sale_edit.html", template_context(request, **form_context))


@router.post("/operations/sales/{kind}/{row_id}/edit", name="edit_sale")
@router.post("/sales/{kind}/{row_id}/edit", name="compat_edit_sale_submit")
async def edit_sale_submit(
    request: Request, kind: str, row_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)

    service = SalesService(db)
    try:
        schema = SaleFormSchema.model_validate(form)
        await service.edit_sale_from_form(kind, row_id, schema)
        flash(request, "Vente modifiée.", "success")
    except Exception as exc:
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(SALES_FILTER_URL, status_code=303)


@router.post("/operations/sales/{kind}/{row_id}/delete", name="delete_sale")
@router.post("/sales/{kind}/{row_id}/delete", name="compat_delete_sale")
async def delete_sale(
    request: Request, kind: str, row_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, PERMISSION_OPERATIONS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)

    service = SalesService(db)
    if await service.delete_sale_by_id(kind, row_id):
        flash(request, "Vente supprimée et stock corrigé.", "success")
    else:
        flash(request, "Vente introuvable.", "danger")
    return RedirectResponse(SALES_FILTER_URL, status_code=303)
