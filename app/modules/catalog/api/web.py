from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.application.queries import (
    new_catalog_context,
    raw_material_edit_context,
    product_edit_context,
    quick_add_context,
    resolve_name_from_form,
)
from app.modules.catalog.api.schemas import (
    RawMaterialCreateSchema,
    RawMaterialUpdateSchema,
    FinishedProductCreateSchema,
    FinishedProductUpdateSchema,
)
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates

router = APIRouter(tags=["catalog"])


# ── CATALOG LIST ──────────────────────────────────────────────────────────────


@router.get("/catalog", name="catalog")
async def catalog_page(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.read")
    if denied:
        return denied

    service = CatalogService(db)
    context = await service.catalog_context(request.query_params, request.url.path)
    return templates.TemplateResponse(
        "catalog.html", template_context(request, **context)
    )


# ── COMPATIBILITY REDIRECTS ───────────────────────────────────────────────────


@router.api_route("/raw-materials", methods=["GET", "POST"], name="raw_materials")
async def raw_materials_page(request: Request):
    denied = require_permission(request, "catalog.read")
    if denied:
        return denied
    return RedirectResponse("/catalog", status_code=303)


@router.api_route("/products", methods=["GET", "POST"], name="products")
async def products_page(request: Request):
    denied = require_permission(request, "catalog.read")
    if denied:
        return denied
    return RedirectResponse("/catalog", status_code=303)


# ── NEW CATALOG ITEM ──────────────────────────────────────────────────────────


@router.get("/catalog/new", name="new_catalog_item")
async def new_catalog_item_page(request: Request):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied
    kind = request.query_params.get("kind", "raw")
    return templates.TemplateResponse(
        "catalog_new.html", template_context(request, **new_catalog_context(kind))
    )


@router.post("/catalog/new", name="new_catalog_item")
async def new_catalog_item_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()

    kind = str(form.get("kind", "raw")).strip()
    name = resolve_name_from_form(form, kind)

    # Convert form to a dict and update resolved name
    data = {k: v for k, v in form.items()}
    data["name"] = name

    service = CatalogService(db)

    try:
        if kind == "raw":
            schema = RawMaterialCreateSchema(**data)
            await service.create_raw_material(schema)
        else:
            schema = FinishedProductCreateSchema(**data)
            await service.create_finished_product(schema)

        flash(
            request,
            "Matière première ajoutée avec succès."
            if kind == "raw"
            else "Produit final ajouté avec succès.",
            "success",
        )
        return RedirectResponse("/catalog", status_code=303)

    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return templates.TemplateResponse(
            "catalog_new.html",
            template_context(request, **new_catalog_context(kind)),
        )


# ── EDIT RAW MATERIAL ─────────────────────────────────────────────────────────


@router.get("/raw-materials/{material_id}/edit", name="edit_raw_material")
async def edit_raw_material_page(
    request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied

    service = CatalogService(db)
    material = await service.get_raw_material(material_id)
    if not material:
        flash(request, "Matière introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)

    context = raw_material_edit_context(material)
    return templates.TemplateResponse(
        "raw_material_edit.html", template_context(request, **context)
    )


@router.post("/raw-materials/{material_id}/edit", name="edit_raw_material")
async def edit_raw_material_submit(
    request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied
    await csrf_protect(request)

    service = CatalogService(db)
    material = await service.get_raw_material(material_id)
    if not material:
        flash(request, "Matière introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)

    form = await request.form()
    name = resolve_name_from_form(form, "raw")

    data = {k: v for k, v in form.items()}
    data["name"] = name

    try:
        schema = RawMaterialUpdateSchema(**data)
        await service.update_raw_material(material_id, schema)
        flash(request, "Matière première modifiée.", "success")
        return RedirectResponse("/catalog", status_code=303)
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        context = raw_material_edit_context(material)
        return templates.TemplateResponse(
            "raw_material_edit.html", template_context(request, **context)
        )


# ── EDIT PRODUCT ──────────────────────────────────────────────────────────────


@router.get("/products/{product_id}/edit", name="edit_product")
async def edit_product_page(
    request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied

    service = CatalogService(db)
    product = await service.get_product(product_id)
    if not product:
        flash(request, "Produit introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)

    context = product_edit_context(product)
    return templates.TemplateResponse(
        "product_edit.html", template_context(request, **context)
    )


@router.post("/products/{product_id}/edit", name="edit_product")
async def edit_product_submit(
    request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.write")
    if denied:
        return denied
    await csrf_protect(request)

    service = CatalogService(db)
    product = await service.get_product(product_id)
    if not product:
        flash(request, "Produit introuvable.", "danger")
        return RedirectResponse("/catalog", status_code=303)

    form = await request.form()
    name = resolve_name_from_form(form, "finished")

    data = {k: v for k, v in form.items()}
    data["name"] = name

    try:
        schema = FinishedProductUpdateSchema(**data)
        await service.update_finished_product(product_id, schema)
        flash(request, "Produit modifié.", "success")
        return RedirectResponse("/catalog", status_code=303)
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        context = product_edit_context(product)
        return templates.TemplateResponse(
            "product_edit.html", template_context(request, **context)
        )


# ── DELETE RAW MATERIAL ───────────────────────────────────────────────────────


@router.post("/raw-materials/{material_id}/delete", name="delete_raw_material")
async def delete_raw_material(
    request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.delete")
    if denied:
        return denied
    await csrf_protect(request)

    service = CatalogService(db)
    success = await service.delete_raw_material(material_id)
    if success:
        flash(request, "Matière première supprimée.", "success")
    else:
        flash(
            request,
            "Impossible de supprimer une matière avec historique.",
            "danger",
        )
    return RedirectResponse("/catalog", status_code=303)


# ── DELETE PRODUCT ────────────────────────────────────────────────────────────


@router.post("/products/{product_id}/delete", name="delete_product")
async def delete_product(
    request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "catalog.delete")
    if denied:
        return denied
    await csrf_protect(request)

    service = CatalogService(db)
    success = await service.delete_finished_product(product_id)
    if success:
        flash(request, "Produit fini supprimé.", "success")
    else:
        flash(
            request,
            "Impossible de supprimer un produit avec historique.",
            "danger",
        )
    return RedirectResponse("/catalog", status_code=303)


# ── QUICK ADD ─────────────────────────────────────────────────────────────────


@router.get("/quick-add", name="quick_add")
async def quick_add_page(request: Request):
    denied = require_permission(request, "tools.read")
    if denied:
        return denied
    default_target = request.query_params.get("target", "client")
    return templates.TemplateResponse(
        "quick_add.html",
        template_context(request, **quick_add_context(default_target)),
    )
