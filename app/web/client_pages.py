from __future__ import annotations


from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.permissions import PERMISSION_CONTACTS_READ, PERMISSION_CONTACTS_WRITE
from app.services.client_service import (
    create_client_from_form,
    import_clients_from_files,
    import_clients_from_preview,
    preview_clients_from_files,
)
from app.schemas.client_validation import ClientValidationSchema
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates


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
        create_client_from_form(validated.model_dump())
        flash(request, "Client ajouté avec succès.", "success")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    except Exception as e:
        from app.core.exceptions import get_friendly_error_message
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(NEW_CLIENT_URL, status_code=303)


@router.get("/clients/new", name="compat_new_client")
async def compat_new_client_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_CLIENT_URL, status_code=303)




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
        flash(request, f"Import terminé : {result['created']} client(s) créés, {result['updated']} mis à jour avec dernier solde.", "success")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    files = form.getlist("excel_files")
    if not files:
        flash(request, "Ajoutez au moins un fichier Excel.", "warning")
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
    flash(request, f"Import terminé : {result['created']} client(s) créés, {result['updated']} mis à jour avec dernier solde.", level)
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.get("/clients/{client_id}", name="compat_client_detail")
async def compat_client_detail(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}", status_code=303)




@router.get("/clients/{client_id}/print-history", name="compat_print_client_history")
async def compat_print_client_history(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/print-history", status_code=303)




@router.get("/clients/{client_id}/edit", name="compat_edit_client")
async def compat_edit_client_page(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/edit", status_code=303)



