from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.activity import log_activity
from app.core.db_access import execute_db, query_db
from app.core.permissions import PERMISSION_CONTACTS_DELETE, PERMISSION_CONTACTS_READ, PERMISSION_CONTACTS_WRITE
from app.core.storage import backup_database
from app.repositories.client_repository import get_client
from app.services.client_service import (
    create_client_from_form,
    get_client_detail_context,
    import_clients_from_files,
    import_clients_from_preview,
    preview_clients_from_files,
    update_client_from_form,
)
from app.services.print_service import COMPANY_INFO
from app.schemas.client_validation import ClientValidationSchema
from app.web.deps import csrf_protect, flash, get_current_user, require_permission, template_context, templates


router = APIRouter()


def _history_not_found_response() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;font-family:Arial,sans-serif;background:#f8fafc;color:#111827;display:grid;place-items:center;min-height:100vh;">
  <main style="max-width:520px;padding:24px;text-align:center;">
    <h1 style="font-size:1.25rem;margin:0 0 8px;">Historique client introuvable.</h1>
    <p style="margin:0;color:#64748b;">Le client demande n'existe plus ou n'est pas disponible.</p>
  </main>
</body>
</html>""",
        status_code=404,
    )

CLIENTS_FILTER_URL = "/contacts?type=client"
NEW_CLIENT_URL = "/contacts/clients/new"
IMPORT_CLIENTS_URL = "/contacts/clients/import-excel"


@router.get("/clients", name="clients")
async def clients_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.post("/clients", name="clients")
async def clients_submit(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = ClientValidationSchema(**data)
    except Exception as e:
        from pydantic import ValidationError
        errors = [err["msg"] for err in e.errors()] if isinstance(e, ValidationError) else [str(e)]
        flash(request, f"Erreur de validation : {', '.join(errors)}", "danger")
        return RedirectResponse(NEW_CLIENT_URL, status_code=303)
        
    create_client_from_form(validated.model_dump())
    flash(request, "Client ajoute avec succes.", "success")
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.get("/clients/new", name="compat_new_client")
async def compat_new_client_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_CLIENT_URL, status_code=303)


@router.get("/contacts/clients/new", name="new_client")
async def new_client_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return templates.TemplateResponse("client_new.html", template_context(request))


@router.post("/contacts/clients/new", name="new_client")
@router.post("/clients/new", name="compat_new_client_submit")
async def new_client_submit(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = ClientValidationSchema(**data)
    except Exception as e:
        from pydantic import ValidationError
        errors = [err["msg"] for err in e.errors()] if isinstance(e, ValidationError) else [str(e)]
        flash(request, f"Erreur de validation : {', '.join(errors)}", "danger")
        return templates.TemplateResponse(
            "client_new.html",
            template_context(request, client=form)
        )
        
    create_client_from_form(validated.model_dump())
    flash(request, "Client ajoute avec succes.", "success")
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.get("/clients/import-excel", name="compat_import_clients_excel")
async def compat_import_clients_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(IMPORT_CLIENTS_URL, status_code=303)


@router.get("/contacts/clients/import-excel", name="import_clients_excel")
async def import_clients_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return templates.TemplateResponse("client_import.html", template_context(request))


@router.post("/contacts/clients/import-excel", name="import_clients_excel")
@router.post("/clients/import-excel", name="compat_import_clients_excel_submit")
async def import_clients_submit(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    action = str(form.get("action", "import") or "import").strip()
    if action == "confirm_preview":
        result = import_clients_from_preview(str(form.get("preview_token", "") or ""))
        for err in result["errors"][:5]:
            flash(request, err, "danger")
        if result["errors"]:
            preview = {
                "rows": result.get("preview", []),
                "errors": result["errors"],
                "duplicates": [],
                "created": 0,
                "updated": 0,
                "token": "",
            }
            return templates.TemplateResponse("client_import.html", template_context(request, preview=preview))
        flash(request, f"Import termine : {result['created']} client(s) crees, {result['updated']} mis a jour avec dernier solde.", "success")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    files = form.getlist("excel_files")
    if not files:
        flash(request, "Ajoute au moins un fichier Excel.", "warning")
        return RedirectResponse(IMPORT_CLIENTS_URL, status_code=303)

    if action == "preview":
        result = preview_clients_from_files(files)
        for err in result["errors"][:5]:
            flash(request, err, "danger")
        for name in result["duplicates"][:5]:
            flash(request, f"Doublon dans les fichiers: {name}", "warning")
        return templates.TemplateResponse("client_import.html", template_context(request, preview=result))

    result = import_clients_from_files(files)
    for err in result["errors"][:5]:
        flash(request, err, "danger")
    level = "success" if (result["created"] or result["updated"]) else "warning"
    flash(request, f"Import termine : {result['created']} client(s) crees, {result['updated']} mis a jour avec dernier solde.", level)
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.get("/clients/{client_id}", name="compat_client_detail")
async def compat_client_detail(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}", status_code=303)


@router.get("/contacts/clients/{client_id}", name="client_detail")
async def client_detail(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    context = get_client_detail_context(client_id)
    if not context:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("client_detail.html", template_context(request, **context))


@router.get("/clients/{client_id}/print-history", name="compat_print_client_history")
async def compat_print_client_history(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/print-history", status_code=303)


@router.get("/contacts/clients/{client_id}/print-history", name="print_client_history")
async def print_client_history(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    context = get_client_detail_context(client_id)
    if not context:
        return _history_not_found_response()
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


@router.get("/clients/{client_id}/edit", name="compat_edit_client")
async def compat_edit_client_page(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/edit", status_code=303)


@router.get("/contacts/clients/{client_id}/edit", name="edit_client")
async def edit_client_page(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    client = get_client(client_id)
    if not client:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("client_edit.html", template_context(request, client=client))


@router.post("/contacts/clients/{client_id}/edit", name="edit_client")
@router.post("/clients/{client_id}/edit", name="compat_edit_client_submit")
async def edit_client_submit(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    client = get_client(client_id)
    if not client:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = ClientValidationSchema(**data)
    except Exception as e:
        from pydantic import ValidationError
        errors = [err["msg"] for err in e.errors()] if isinstance(e, ValidationError) else [str(e)]
        flash(request, f"Erreur de validation : {', '.join(errors)}", "danger")
        
        # Merge id to form dict for template cancel link
        form_dict = dict(form)
        form_dict["id"] = client_id
        return templates.TemplateResponse(
            "client_edit.html",
            template_context(request, client=form_dict)
        )
        
    update_client_from_form(client_id, validated.model_dump())
    flash(request, "Client modifie avec succes.", "success")
    return RedirectResponse(f"/contacts/clients/{client_id}", status_code=303)


@router.post("/contacts/clients/{client_id}/delete", name="delete_client")
@router.post("/clients/{client_id}/delete", name="compat_delete_client")
async def delete_client(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    has_ops = query_db(
        "SELECT 1 FROM sales WHERE client_id = %s UNION SELECT 1 FROM raw_sales WHERE client_id = %s UNION SELECT 1 FROM payments WHERE client_id = %s LIMIT 1",
        (client_id, client_id, client_id),
        one=True,
    )
    if has_ops:
        flash(request, "Impossible de supprimer un client avec historique.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    execute_db("DELETE FROM clients WHERE id = %s", (client_id,))
    log_activity("delete_client", "client", client_id, "Suppression client")
    backup_database("delete_client")
    flash(request, "Client supprime.", "success")
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
