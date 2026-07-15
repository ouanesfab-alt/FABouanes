from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_session
from app.modules.clients.application.services import ClientService
from app.modules.clients.api.schemas import ClientCreateSchema

from app.core.permissions import PERMISSION_CONTACTS_READ, PERMISSION_CONTACTS_WRITE
from app.core.schema.client_validation import ClientValidationSchema
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
async def clients_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated_schema = ClientValidationSchema(**data)
        schema = ClientCreateSchema(
            name=validated_schema.name,
            phone=validated_schema.phone or "",
            address=validated_schema.address or "",
            notes=validated_schema.notes or "",
            opening_credit=validated_schema.opening_credit or 0.0
        )
        service = ClientService(db)
        await service.create_client(schema)
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
    
    token = request.query_params.get("preview_token", "").strip()
    preview = None
    if token:
        try:
            from app.modules.clients.application.services import ClientService
            service = ClientService(None)
            rows = service._load_client_import_preview(token)
            if rows:
                seen = set()
                duplicates = []
                for row in rows:
                    name_key = str(row["name"]).strip().casefold()
                    if name_key in seen:
                        duplicates.append(row["name"])
                    seen.add(name_key)
                
                preview = {
                    "rows": rows,
                    "errors": [],
                    "duplicates": duplicates,
                    "token": token
                }
        except Exception:
            pass
            
    return templates.TemplateResponse("client_import.html", template_context(request, preview=preview))


@router.post("/contacts/clients/import-excel", name="import_clients_excel")
@router.post("/clients/import-excel", name="compat_import_clients_excel_submit")
async def import_clients_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    action = str(form.get("action", "import") or "import").strip()
    service = ClientService(db)

    if action == "confirm_preview":
        result = await service.import_clients_from_preview(str(form.get("preview_token", "") or ""))
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
        result = await service.preview_clients_from_files(files)
        for err in result["errors"][:5]:
            flash(request, err, "danger")
        for name in result["duplicates"][:5]:
            flash(request, f"Doublon dans les fichiers: {name}", "warning")
        return templates.TemplateResponse("client_import.html", template_context(request, preview=result))

    result = await service.import_clients_from_files(files)
    for err in result["errors"][:5]:
        flash(request, err, "danger")
    level = "success" if (result["created"] or result["updated"]) else "warning"
    flash(request, f"Import terminé : {result['created']} client(s) créés, {result['updated']} mis à jour avec dernier solde.", level)
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.get("/contacts/clients/import/preview-client")
async def preview_client_import(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    token = request.query_params.get("token", "").strip()
    index = int(request.query_params.get("index", "-1"))
    if not token or index < 0:
        return HTMLResponse("Paramètres invalides", status_code=400)
    
    try:
        from app.modules.clients.application.services import ClientService
        # On initialise le service sans session puisqu'on ne fait que lire le JSON de preview
        service = ClientService(None)
        rows = service._load_client_import_preview(token)
        if index >= len(rows):
            return HTMLResponse("Index hors limites", status_code=404)
        
        row = rows[index]
        return templates.TemplateResponse("client_import_preview_single.html", template_context(request, row=row))
    except Exception as e:
        return HTMLResponse(f"Erreur: {e}", status_code=500)


@router.post("/contacts/clients/import/import-single-file")
async def import_single_client_file(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=403)
    await csrf_protect(request)
    
    form = await request.form()
    file_obj = form.get("excel_file")
    if not file_obj or not file_obj.filename:
        return JSONResponse({"success": False, "error": "Aucun fichier fourni"}, status_code=400)
    
    from app.modules.clients.application.services import ClientService
    service = ClientService(db)
    result = await service.import_clients_from_files([file_obj])
    
    if result["errors"]:
        return JSONResponse({"success": False, "errors": result["errors"]})
    
    status_type = "create" if result["created"] > 0 else "update"
    return JSONResponse({
        "success": True,
        "filename": file_obj.filename,
        "status": status_type,
        "created": result["created"],
        "updated": result["updated"]
    })


@router.post("/contacts/clients/import/import-preview-single-row")
async def import_preview_single_row(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=403)
    await csrf_protect(request)
    
    body = await request.json()
    token = body.get("token", "").strip()
    index = int(body.get("index", "-1"))
    
    if not token or index < 0:
        return JSONResponse({"success": False, "error": "Paramètres invalides"}, status_code=400)
    
    from app.modules.clients.application.services import ClientService
    service = ClientService(db)
    try:
        rows = service._load_client_import_preview(token)
        if index >= len(rows):
            return JSONResponse({"success": False, "error": "Index hors limites"}, status_code=404)
        
        row = rows[index]
        result = await service._import_parsed_client_rows([row])
        if result["errors"]:
            return JSONResponse({"success": False, "errors": result["errors"]})
        
        status_type = "create" if result["created"] > 0 else "update"
        return JSONResponse({
            "success": True,
            "client_name": row["name"],
            "status": status_type
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/contacts/clients/import/clear-preview")
async def clear_preview_token(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=403)
    await csrf_protect(request)
    body = await request.json()
    token = body.get("token", "").strip()
    if token:
        from app.modules.clients.application.services import ClientService
        service = ClientService(None)
        service._discard_client_import_preview(token)
    return JSONResponse({"success": True})


@router.post("/contacts/clients/import/preview-single-file")
async def preview_single_client_file(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=403)
    await csrf_protect(request)
    
    form = await request.form()
    file_obj = form.get("excel_file")
    if not file_obj or not file_obj.filename:
        return JSONResponse({"success": False, "error": "Aucun fichier fourni"}, status_code=400)
    
    from app.modules.clients.application.services import ClientService
    service = ClientService(db)
    try:
        result = await service.preview_clients_from_files([file_obj])
        if result["errors"]:
            return JSONResponse({"success": False, "error": result["errors"][0]})
        if not result["rows"]:
            return JSONResponse({"success": False, "error": "Fichier vide ou invalide"})
        
        return JSONResponse({
            "success": True,
            "row": result["rows"][0]
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/contacts/clients/import/save-preview-token")
async def save_preview_token_endpoint(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=403)
    await csrf_protect(request)
    
    body = await request.json()
    rows = body.get("rows")
    if not rows:
        return JSONResponse({"success": False, "error": "Aucune donnée de prévisualisation"}, status_code=400)
        
    from app.modules.clients.application.services import ClientService
    service = ClientService(None)
    token = service._save_client_import_preview(rows)
    return JSONResponse({"success": True, "token": token})


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
