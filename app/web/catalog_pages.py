from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.services.catalog_service import (
    catalog_context,
    create_catalog_item_from_form,
    delete_product_by_id,
    delete_raw_material_by_id,
    get_product,
    get_raw_material,
    new_catalog_context,
    product_edit_context,
    quick_add_context,
    raw_material_edit_context,
    update_product_from_form,
    update_raw_material_from_form,
)
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.permissions import (
    PERMISSION_CATALOG_DELETE,
    PERMISSION_CATALOG_READ,
    PERMISSION_CATALOG_WRITE,
    PERMISSION_TOOLS_READ,
)


router = APIRouter()


@router.get("/catalog", name="catalog")
async def catalog_page(request: Request):
    denied = require_permission(request, PERMISSION_CATALOG_READ)
    if denied:
        return denied
    return templates.TemplateResponse("catalog.html", template_context(request, **catalog_context(request.query_params, request.url.path)))


@router.api_route("/raw-materials", methods=["GET", "POST"], name="raw_materials")
async def raw_materials_page(request: Request):
    denied = require_permission(request, PERMISSION_CATALOG_READ)
    if denied:
        return denied
    return RedirectResponse("/catalog", status_code=303)


@router.api_route("/products", methods=["GET", "POST"], name="products")
async def products_page(request: Request):
    denied = require_permission(request, PERMISSION_CATALOG_READ)
    if denied:
        return denied
    return RedirectResponse("/catalog", status_code=303)


@router.get("/catalog/new", name="new_catalog_item")
async def new_catalog_item_page(request: Request):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    kind = request.query_params.get("kind", "raw")
    return templates.TemplateResponse("catalog_new.html", template_context(request, **new_catalog_context(kind)))


@router.post("/catalog/new", name="new_catalog_item")
async def new_catalog_item_submit(request: Request):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    kind, _item_id = create_catalog_item_from_form(form)
    flash(request, "Matière première ajoutée avec succès." if kind == "raw" else "Produit final ajouté avec succès.", "success")
    return RedirectResponse("/catalog", status_code=303)


@router.get("/raw-materials/{material_id}/edit", name="edit_raw_material")
async def edit_raw_material_page(request: Request, material_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    context = raw_material_edit_context(material_id)
    if not context:
        flash(request, "Matière introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)
    return templates.TemplateResponse("raw_material_edit.html", template_context(request, **context))


@router.post("/raw-materials/{material_id}/edit", name="edit_raw_material")
async def edit_raw_material_submit(request: Request, material_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    if not get_raw_material(material_id):
        flash(request, "Matière introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)
    form = await request.form()
    update_raw_material_from_form(material_id, form)
    flash(request, "Matière première modifiée.", "success")
    return RedirectResponse("/catalog", status_code=303)


@router.get("/products/{product_id}/edit", name="edit_product")
async def edit_product_page(request: Request, product_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    context = product_edit_context(product_id)
    if not context:
        flash(request, "Produit introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)
    return templates.TemplateResponse("product_edit.html", template_context(request, **context))


@router.post("/products/{product_id}/edit", name="edit_product")
async def edit_product_submit(request: Request, product_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    if not get_product(product_id):
        flash(request, "Produit introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)
    form = await request.form()
    update_product_from_form(product_id, form)
    flash(request, "Produit modifié.", "success")
    return RedirectResponse("/catalog", status_code=303)


@router.post("/raw-materials/{material_id}/delete", name="delete_raw_material")
async def delete_raw_material(request: Request, material_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    if delete_raw_material_by_id(material_id):
        flash(request, "Matière première supprimée.", "success")
    else:
        flash(request, "Impossible de supprimer une matière avec historique.", "danger")
    return RedirectResponse("/catalog", status_code=303)


@router.post("/products/{product_id}/delete", name="delete_product")
async def delete_product(request: Request, product_id: int):
    denied = require_permission(request, PERMISSION_CATALOG_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    if delete_product_by_id(product_id):
        flash(request, "Produit fini supprimé.", "success")
    else:
        flash(request, "Impossible de supprimer un produit avec historique.", "danger")
    return RedirectResponse("/catalog", status_code=303)


@router.get("/quick-add", name="quick_add")
async def quick_add_page(request: Request):
    denied = require_permission(request, PERMISSION_TOOLS_READ)
    if denied:
        return denied
    default_target = request.query_params.get("target", "client")
    return templates.TemplateResponse("quick_add.html", template_context(request, **quick_add_context(default_target)))
