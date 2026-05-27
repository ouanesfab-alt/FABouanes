from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.modules.clients.service import ClientService
from app.modules.clients.schemas_validation import ClientCreateSchema, ClientUpdateSchema
from app.services.print_service import COMPANY_INFO
from app.web.deps import (
    csrf_protect,
    flash,
    get_current_user,
    require_permission,
    template_context,
    templates,
)

CLIENTS_FILTER_URL = "/contacts?type=client"

router = APIRouter(prefix="/contacts/clients", tags=["clients"])


# ── LIST ──────────────────────────────────────────────────────────────────────


@router.get("", name="clients_list")
async def list_clients_page(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.read")
    if denied:
        return denied

    search = request.query_params.get("q", "").strip()
    page = int(request.query_params.get("page", 1))

    service = ClientService(db)
    clients, total = await service.list_clients(search=search, page=page, page_size=20)

    return templates.TemplateResponse(
        "contacts.html",
        template_context(
            request, contacts=clients, total=total, search=search, kind="client"
        ),
    )


# ── CREATE ────────────────────────────────────────────────────────────────────


@router.get("/new", name="compat_new_client")
async def new_client_page(request: Request):
    denied = require_permission(request, "contacts.write")
    if denied:
        return denied
    return RedirectResponse("/contacts/new?kind=client", status_code=303)


@router.post("/new", name="new_client")
async def new_client_submit(
    request: Request, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.write")
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = ClientCreateSchema(**data)
        service = ClientService(db)
        await service.create_client(validated)
        flash(request, "Client ajouté avec succès.", "success")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return templates.TemplateResponse(
            "contact_new.html",
            template_context(request, client=form, kind="client"),
        )


# ── DETAIL ────────────────────────────────────────────────────────────────────


@router.get("/{client_id}", name="client_detail")
async def client_detail(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.read")
    if denied:
        return denied

    service = ClientService(db)
    context = await service.get_client_detail_context(client_id)
    if not context:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    return templates.TemplateResponse(
        "client_detail.html", template_context(request, **context)
    )


# ── EDIT ──────────────────────────────────────────────────────────────────────


@router.get("/{client_id}/edit", name="edit_client")
async def edit_client_page(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.write")
    if denied:
        return denied

    service = ClientService(db)
    client = await service.get_client(client_id)
    if not client:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    # Convert to dict for template compatibility
    client_dict = {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "address": client.address,
        "notes": client.notes,
        "opening_credit": client.opening_credit,
    }
    return templates.TemplateResponse(
        "client_edit.html", template_context(request, client=client_dict)
    )


@router.post("/{client_id}/edit", name="edit_client_submit")
async def edit_client_submit(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.write")
    if denied:
        return denied
    await csrf_protect(request)

    service = ClientService(db)
    client = await service.get_client(client_id)
    if not client:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = ClientUpdateSchema(**data)
        updated = await service.update_client(client_id, validated)
        flash(request, "Client modifié avec succès.", "success")
        return RedirectResponse(
            f"/contacts/clients/{client_id}", status_code=303
        )
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        form_dict = dict(form)
        form_dict["id"] = client_id
        return templates.TemplateResponse(
            "client_edit.html",
            template_context(request, client=form_dict),
        )


# ── DELETE ────────────────────────────────────────────────────────────────────


@router.post("/{client_id}/delete", name="delete_client")
async def delete_client(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.delete")
    if denied:
        return denied
    await csrf_protect(request)

    service = ClientService(db)
    has_ops = await service.has_operations(client_id)
    if has_ops:
        flash(request, "Impossible de supprimer un client avec historique.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    success = await service.delete_client(client_id)
    if success:
        flash(request, "Client supprimé.", "success")
    else:
        flash(request, "Client introuvable.", "danger")
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


# ── HISTORY ───────────────────────────────────────────────────────────────────


@router.get("/{client_id}/history", name="client_history_page")
async def client_history_page(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.read")
    if denied:
        return denied

    try:
        page = int(request.query_params.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    service = ClientService(db)
    context = await service.get_history_page_context(client_id, page=page)
    if not context:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    return templates.TemplateResponse(
        "clients/history.html", template_context(request, **context)
    )


# ── PRINT HISTORY ─────────────────────────────────────────────────────────────


@router.get("/{client_id}/print-history", name="print_client_history")
async def print_client_history(
    request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)
):
    denied = require_permission(request, "contacts.read")
    if denied:
        return denied

    service = ClientService(db)
    context = await service.get_client_detail_context(client_id)
    if not context:
        return HTMLResponse(
            """<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;font-family:Arial,sans-serif;background:#f8fafc;color:#111827;display:grid;place-items:center;min-height:100vh;">
  <main style="max-width:520px;padding:24px;text-align:center;">
    <h1 style="font-size:1.25rem;margin:0 0 8px;">Historique client introuvable.</h1>
    <p style="margin:0;color:#64748b;">Le client demandé n'existe plus ou n'est pas disponible.</p>
  </main>
</body>
</html>""",
            status_code=404,
        )

    printed_at = datetime.now()
    user = get_current_user(request) or {}
    return templates.TemplateResponse(
        "client_history_print.html",
        template_context(
            request,
            company=COMPANY_INFO,
            printed_date=printed_at.strftime("%Y-%m-%d"),
            printed_time=printed_at.strftime("%H:%M"),
            printed_by=user.get("username", ""),
            **context,
        ),
    )
