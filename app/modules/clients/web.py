from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.exceptions import get_friendly_error_message
from app.core.permissions import (
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
)
from app.infra.printing import COMPANY_INFO
from app.modules.clients.directory_service import (
    contacts_context,
    create_supplier_from_form,
    delete_supplier_by_id,
    get_supplier,
    get_supplier_detail_context,
    update_supplier_from_form,
)
from app.modules.clients.schemas import (
    ClientCreateSchema,
    ClientUpdateSchema,
    ClientValidationSchema,
)
from app.modules.clients.service import ClientService
from app.modules.purchases.schemas import SupplierValidationSchema
from app.web.deps import (
    csrf_protect,
    flash,
    get_current_user,
    require_permission,
    template_context,
    templates,
)

router = APIRouter(tags=["contacts"])

CLIENTS_FILTER_URL = "/contacts?type=client"
SUPPLIERS_FILTER_URL = "/contacts?type=supplier"
NEW_CLIENT_URL = "/contacts/clients/new"
NEW_SUPPLIER_URL = "/contacts/suppliers/new"
IMPORT_CLIENTS_URL = "/contacts/clients/import-excel"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONTACTS OVERVIEW & COMMON
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/contacts", name="contacts")
async def contacts_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    filter_type = request.query_params.get("type", "all")
    filter_name = request.query_params.get("name", "")
    return templates.TemplateResponse(
        "contacts.html",
        template_context(
            request, **await contacts_context(filter_type, filter_name, request.query_params, request.url.path, db=db)
        ),
    )


@router.get("/contacts/new", name="new_contact")
async def new_contact_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    kind = request.query_params.get("kind", "client")
    return templates.TemplateResponse("contact_new.html", template_context(request, kind=kind))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CLIENT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/clients", name="clients")
async def clients_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


@router.post("/clients", name="clients_create_legacy")
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
            opening_credit=validated_schema.opening_credit or 0.0,
            credit_limit=validated_schema.credit_limit,
        )
        service = ClientService(db)
        await service.create_client(schema)
        flash(request, "Client ajouté avec succès.", "success")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    except Exception as e:
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(NEW_CLIENT_URL, status_code=303)


@router.get("/clients/new", name="compat_new_client_redirect")
async def compat_new_client_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(NEW_CLIENT_URL, status_code=303)


@router.get("/contacts/clients", name="clients_list")
async def list_clients_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    query = dict(request.query_params)
    query["type"] = "client"
    return RedirectResponse(f"/contacts?{urlencode(query)}", status_code=303)


@router.get("/contacts/clients/new", name="compat_new_client")
async def new_client_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse("/contacts/new?kind=client", status_code=303)


@router.post("/contacts/clients/new", name="new_client")
async def new_client_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
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
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return templates.TemplateResponse(
            "contact_new.html",
            template_context(request, client=form, kind="client"),
        )


@router.get("/clients/{client_id}", name="compat_client_detail")
async def compat_client_detail(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}", status_code=303)


@router.get("/contacts/clients/{client_id}", name="client_detail")
async def client_detail(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied

    service = ClientService(db)
    context = await service.get_client_detail_context(client_id)
    if not context:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("client_detail.html", template_context(request, **context))


@router.get("/clients/{client_id}/edit", name="compat_edit_client")
async def compat_edit_client_page(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/edit", status_code=303)


@router.get("/contacts/clients/{client_id}/edit", name="edit_client")
async def edit_client_page(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied

    service = ClientService(db)
    client = await service.get_client(client_id)
    if not client:
        flash(request, "Client introuvable.", "danger")
        return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)

    client_dict = {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "address": client.address,
        "notes": client.notes,
        "opening_credit": client.opening_credit,
        "credit_limit": client.credit_limit,
    }
    return templates.TemplateResponse("client_edit.html", template_context(request, client=client_dict))


@router.post("/contacts/clients/{client_id}/edit", name="edit_client_submit")
async def edit_client_submit(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
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
        await service.update_client(client_id, validated)
        flash(request, "Client modifié avec succès.", "success")
        return RedirectResponse(f"/contacts/clients/{client_id}", status_code=303)
    except Exception as e:
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        form_dict = dict(form)
        form_dict["id"] = client_id
        return templates.TemplateResponse(
            "client_edit.html",
            template_context(request, client=form_dict),
        )


@router.post("/contacts/clients/{client_id}/delete", name="delete_client")
async def delete_client(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_DELETE)
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


@router.get("/contacts/clients/{client_id}/history", name="client_history_page")
async def client_history_page(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
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

    return templates.TemplateResponse("clients/history.html", template_context(request, **context))


@router.get("/clients/{client_id}/print-history", name="compat_print_client_history")
async def compat_print_client_history(request: Request, client_id: int):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(f"/contacts/clients/{client_id}/print-history", status_code=303)


@router.get("/contacts/clients/{client_id}/print-history", name="print_client_history")
async def print_client_history(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
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


@router.post("/contacts/clients/{client_id}/shred", name="shred_client")
async def shred_client_route(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    service = ClientService(db)
    success = await service.shred_client(client_id)
    if success:
        flash(request, "Données client détruites (Crypto-Shredding).", "success")
    else:
        flash(request, "Client introuvable.", "danger")
    return RedirectResponse(CLIENTS_FILTER_URL, status_code=303)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EXCEL IMPORT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════


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

                preview = {"rows": rows, "errors": [], "duplicates": duplicates, "token": token}
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
        flash(
            request,
            f"Import terminé : {result['created']} client(s) créés, {result['updated']} mis à jour avec dernier solde.",
            "success",
        )
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
    flash(
        request,
        f"Import terminé : {result['created']} client(s) créés, {result['updated']} mis à jour avec dernier solde.",
        level,
    )
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

    service = ClientService(db)
    result = await service.import_clients_from_files([file_obj])

    if result["errors"]:
        return JSONResponse({"success": False, "errors": result["errors"]})

    status_type = "create" if result["created"] > 0 else "update"
    return JSONResponse(
        {
            "success": True,
            "filename": file_obj.filename,
            "status": status_type,
            "created": result["created"],
            "updated": result["updated"],
        }
    )


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
        return JSONResponse({"success": True, "client_name": row["name"], "status": status_type})
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

    service = ClientService(db)
    try:
        result = await service.preview_clients_from_files([file_obj])
        if result["errors"]:
            return JSONResponse({"success": False, "error": result["errors"][0]})
        if not result["rows"]:
            return JSONResponse({"success": False, "error": "Fichier vide ou invalide"})

        return JSONResponse({"success": True, "row": result["rows"][0]})
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

    service = ClientService(None)
    token = service._save_client_import_preview(rows)
    return JSONResponse({"success": True, "token": token})


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SUPPLIER ROUTES
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/suppliers", name="suppliers")
async def suppliers_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.post("/suppliers", name="suppliers")
async def suppliers_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        await create_supplier_from_form(validated.model_dump(), db=db)
        flash(request, "Fournisseur ajouté avec succès.", "success")
    except Exception as e:
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


@router.get("/contacts/suppliers/new", name="new_supplier")
async def new_supplier_page(request: Request):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    return RedirectResponse("/contacts/new?kind=supplier", status_code=303)


@router.post("/contacts/suppliers/new", name="new_supplier")
@router.post("/suppliers/new", name="compat_new_supplier_submit")
async def new_supplier_submit(request: Request, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        await create_supplier_from_form(validated.model_dump(), db=db)
        flash(request, "Fournisseur ajouté avec succès.", "success")
    except Exception as e:
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
async def supplier_detail(request: Request, supplier_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_READ)
    if denied:
        return denied
    context = await get_supplier_detail_context(supplier_id, request.query_params, request.url.path, db=db)
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
async def edit_supplier_page(request: Request, supplier_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    supplier = await get_supplier(supplier_id, db=db)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    return templates.TemplateResponse("supplier_edit.html", template_context(request, supplier=supplier))


@router.post("/contacts/suppliers/{supplier_id}/edit", name="edit_supplier")
@router.post("/suppliers/{supplier_id}/edit", name="compat_edit_supplier_submit")
async def edit_supplier_submit(request: Request, supplier_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_WRITE)
    if denied:
        return denied
    await csrf_protect(request)
    supplier = await get_supplier(supplier_id, db=db)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    form = await request.form()
    try:
        data = {k: v for k, v in form.items()}
        validated = SupplierValidationSchema(**data)
        await update_supplier_from_form(supplier_id, validated.model_dump(), db=db)
        flash(request, "Fournisseur modifié.", "success")
    except Exception as e:
        friendly = get_friendly_error_message(e)
        flash(request, f"Erreur de validation : {friendly}", "danger")
        return RedirectResponse(str(request.url), status_code=303)
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)


@router.post("/contacts/suppliers/{supplier_id}/delete", name="delete_supplier")
@router.post("/suppliers/{supplier_id}/delete", name="compat_delete_supplier")
async def delete_supplier(request: Request, supplier_id: int, db: AsyncSession = Depends(get_async_session)):
    denied = require_permission(request, PERMISSION_CONTACTS_DELETE)
    if denied:
        return denied
    await csrf_protect(request)
    supplier = await get_supplier(supplier_id, db=db)
    if not supplier:
        flash(request, "Fournisseur introuvable.", "danger")
        return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
    try:
        await delete_supplier_by_id(supplier_id, db=db)
        flash(request, "Fournisseur supprimé.", "success")
    except Exception as e:
        flash(request, str(e), "danger")
    return RedirectResponse(SUPPLIERS_FILTER_URL, status_code=303)
