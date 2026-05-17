from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.request_state import set_state_value
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.permissions import PERMISSION_PRODUCTION_DELETE, PERMISSION_PRODUCTION_READ, PERMISSION_PRODUCTION_WRITE
from app.core.helpers import wants_print_after_submit
from app.services.production_service import create_production_from_form, delete_production_by_id, new_production_context, productions_context


router = APIRouter()


@router.get("/production", name="production")
async def production_page(request: Request):
    denied = require_permission(request, PERMISSION_PRODUCTION_READ)
    if denied:
        return denied
    return templates.TemplateResponse("production.html", template_context(request, **productions_context(request.query_params)))


@router.post("/production", name="production")
async def production_submit(request: Request):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    try:
        create_production_from_form(form)
        flash(request, "Production multi-matieres enregistree avec cout de revient.", "success")
    except Exception as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse("/production", status_code=303)


@router.get("/production/new", name="new_production")
async def new_production_page(request: Request):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    return templates.TemplateResponse("production_new.html", template_context(request, **new_production_context()))


@router.post("/production/new", name="new_production")
async def new_production_submit(request: Request):
    denied = require_permission(request, PERMISSION_PRODUCTION_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    set_state_value("submitted_form", form)
    try:
        result = create_production_from_form(form)
        if result["recipe_id"]:
            flash(request, f"Production enregistree. Recette sauvegardee ({result['recipe_label']}). Reste theorique: {result['remainder']:.2f} kg.", "success")
        else:
            flash(request, f"Production enregistree avec recette et cout de revient. Reste theorique: {result['remainder']:.2f} kg.", "success")
        if wants_print_after_submit():
            return RedirectResponse(f"/print/production/{result['batch_id']}", status_code=303)
        return RedirectResponse("/production", status_code=303)
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse("/production/new", status_code=303)


@router.post("/production/{batch_id}/delete", name="delete_production")
async def delete_production(request: Request, batch_id: int):
    denied = require_permission(request, PERMISSION_PRODUCTION_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    if delete_production_by_id(batch_id):
        flash(request, "Production supprimee et stock corrige.", "success")
    else:
        flash(request, "Impossible de supprimer cette production.", "danger")
    return RedirectResponse("/production", status_code=303)
