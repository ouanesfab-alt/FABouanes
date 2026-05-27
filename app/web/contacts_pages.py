from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.permissions import (
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
)
from app.services.contact_directory_service import (
    contacts_context,
    create_supplier_from_form,
    delete_supplier_by_id,
    get_supplier,
    get_supplier_detail_context,
    update_supplier_from_form,
)
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates


router = APIRouter()

SUPPLIERS_FILTER_URL = "/contacts?type=supplier"
NEW_SUPPLIER_URL = "/contacts/suppliers/new"


@router.get("/contacts", name="contacts")
async def contacts_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    filter_type = request.query_params.get("type", "all")
    filter_name = request.query_params.get("name", "")
    return templates.TemplateResponse(
        "contacts.html",
        template_context(request, **contacts_context(filter_type, filter_name, request.query_params, request.url.path)),
    )


@router.get("/suppliers", name="suppliers")
async def suppliers_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.post("/suppliers", name="suppliers")
async def suppliers_submit(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        from app.schemas.supplier_validation import SupplierValidationSchema
        from pydantic import ValidationError
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        create_supplier_from_form(validated.model_dump())
        flash(request, "Fournisseur ajouté avec succès.", "success")
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(NEW_SUPPLIER_URL, status_code=303)
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.get("/suppliers/new", name="compat_new_supplier")
async def compat_new_supplier_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_SUPPLIER_URL, status_code=303)


@router.get("/contacts/new", name="new_contact")
async def new_contact_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    kind = request.query_params.get("kind", "client")
    return templates.TemplateResponse("contact_new.html", template_context(request, kind=kind))


@router.get("/contacts/suppliers/new", name="new_supplier")
async def new_supplier_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse("/contacts/new?kind=supplier", status_code=303)




@router.post("/contacts/suppliers/new", name="new_supplier")
@router.post("/suppliers/new", name="compat_new_supplier_submit")
async def new_supplier_submit(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        from app.schemas.supplier_validation import SupplierValidationSchema
        from pydantic import ValidationError
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        create_supplier_from_form(validated.model_dump())
        flash(request, "Fournisseur ajouté avec succès.", "success")
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(NEW_SUPPLIER_URL, status_code=303)
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.get("/suppliers/{supplier_id}", name="compat_supplier_detail")
async def compat_supplier_detail(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/suppliers/{supplier_id}", status_code=303)


@router.get("/contacts/suppliers/{supplier_id}", name="supplier_detail")
async def supplier_detail(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    context = get_supplier_detail_context(supplier_id, request.query_params, request.url.path)
    if not context:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("supplier_detail.html", template_context(request, **context))


@router.get("/suppliers/{supplier_id}/edit", name="compat_edit_supplier")
async def compat_edit_supplier_page(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/suppliers/{supplier_id}/edit", status_code=303)


@router.get("/contacts/suppliers/{supplier_id}/edit", name="edit_supplier")
async def edit_supplier_page(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    supplier = get_supplier(supplier_id)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("supplier_edit.html", template_context(request, supplier=supplier))


@router.post("/contacts/suppliers/{supplier_id}/edit", name="edit_supplier")
@router.post("/suppliers/{supplier_id}/edit", name="compat_edit_supplier_submit")
async def edit_supplier_submit(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    supplier = get_supplier(supplier_id)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    form = await request.form()
    try:
        from app.schemas.supplier_validation import SupplierValidationSchema
        from pydantic import ValidationError
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        update_supplier_from_form(supplier_id, validated.model_dump())
        flash(request, "Fournisseur modifié.", "success")
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.post("/contacts/suppliers/{supplier_id}/delete", name="delete_supplier")
@router.post("/suppliers/{supplier_id}/delete", name="compat_delete_supplier")
async def delete_supplier(request: Request, supplier_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    supplier = get_supplier(supplier_id)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    delete_supplier_by_id(supplier_id)
    flash(request, "Fournisseur supprimé.", "success")
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
