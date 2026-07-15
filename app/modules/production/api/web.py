from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.async_db import get_async_session
from app.core.request_state import set_state_value
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.permissions import PERMISSION_PRODUCTION_DELETE, PERMISSION_PRODUCTION_READ, PERMISSION_PRODUCTION_WRITE
from app.core.helpers import wants_print_after_submit

from app.modules.production.application.services import ProductionService
from app.modules.production.api.schemas import ProductionBatchCreate

router = APIRouter(tags=["production"])


def parse_production_form(form) -> dict:
    finished_id_str = form.get("finished_product_id")
    finished_product_id = int(finished_id_str) if finished_id_str else None

    output_qty_str = form.get("output_quantity")
    output_quantity = float(output_qty_str) if output_qty_str else None

    production_date = form.get("production_date")
    notes = form.get("notes")

    raw_ids = form.getlist("raw_material_id[]")
    quantities = form.getlist("quantity[]")

    items = []
    for r_id, qty in zip(raw_ids, quantities):
        if r_id or qty:
            try:
                items.append({
                    "raw_material_id": int(r_id) if r_id else None,
                    "quantity": float(qty) if qty else None
                })
            except ValueError:
                items.append({
                    "raw_material_id": r_id,
                    "quantity": qty
                })

    return {
        "finished_product_id": finished_product_id,
        "output_quantity": output_quantity,
        "production_date": production_date,
        "notes": notes,
        "items": items
    }


@router.get("/production", name="production")
async def production_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_PRODUCTION_READ)
    if denied:
        return denied
    service = ProductionService(db)
    context = await service.productions_context(request.query_params)
    return templates.TemplateResponse("production.html", template_context(request, **context))


@router.post("/production", name="production")
async def production_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    service = ProductionService(db)
    try:
        parsed = parse_production_form(form)
        ProductionBatchCreate.model_validate(parsed)
        await service.create_production_from_form(form)
        flash(request, "Production multi-matières enregistrée avec coût de revient.", "success")
    except Exception as exc:
        from app.core.exceptions import get_friendly_error_message
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
    return RedirectResponse("/production", status_code=303)


@router.get("/production/new", name="new_production")
async def new_production_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    service = ProductionService(db)
    context = await service.new_production_context()
    return templates.TemplateResponse("production_new.html", template_context(request, **context))


@router.post("/production/new", name="new_production")
async def new_production_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    service = ProductionService(db)
    try:
        parsed = parse_production_form(form)
        ProductionBatchCreate.model_validate(parsed)
        result = await service.create_production_from_form(form)
        if result["recipe_id"]:
            flash(request, f"Production enregistrée. Recette sauvegardée ({result['recipe_label']}). Reste théorique : {result['remainder']:.2f} kg.", "success")
        else:
            flash(request, f"Production enregistrée avec recette et coût de revient. Reste théorique : {result['remainder']:.2f} kg.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/production/{result['batch_id']}", status_code=303)
        return RedirectResponse("/production", status_code=303)
    except Exception as exc:
        from app.core.exceptions import get_friendly_error_message
        errors = (
            [err["msg"] for err in exc.errors()]
            if isinstance(exc, ValidationError)
            else [get_friendly_error_message(exc)]
        )
        flash(request, f"Erreur : {', '.join(errors)}", "danger")
        return RedirectResponse("/production/new", status_code=303)


@router.post("/production/{batch_id}/delete", name="delete_production")
async def delete_production(request: Request, batch_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_PRODUCTION_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    service = ProductionService(db)
    if await service.delete_production_by_id(batch_id):
        flash(request, "Production supprimée et stock corrigé.", "success")
    else:
        flash(request, "Impossible de supprimer cette production.", "danger")
    return RedirectResponse("/production", status_code=303)
