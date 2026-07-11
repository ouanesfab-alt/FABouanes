from __future__ import annotations


from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.version import VERSION_LABEL
from app.core.db import postgres_pool_status
from app.core.runtime_paths import paths
from app.services.bon_space_service import find_bon_space_document, list_bon_space_documents
from app.utils.tool_pages import (
    delete_pdf_reader_file,
    get_pdf_reader_file_path,
    list_pdf_reader_files,
    save_pdf_reader_upload,
    list_user_notes,
    save_user_note,
    create_user_note,
    delete_user_note,
)
from app.web.deps import csrf_protect, flash, get_current_user, template_context, templates

router = APIRouter()


@router.get("/notes", name="notes_page")
async def notes_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)

    notes = list_user_notes()
    return templates.TemplateResponse(
        "notes.html",
        template_context(
            request,
            notes=notes,
        ),
    )


@router.post("/notes/api/create", name="notes_api_create")
async def notes_api_create(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        title = str(form.get("title", "") or "Sans titre").strip()
        content = str(form.get("content", "") or "")
        color = str(form.get("color", "yellow") or "yellow").strip()

        note = create_user_note(title, content, color)
        return JSONResponse({"success": True, "note": note})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/notes/api/save", name="notes_api_save")
async def notes_api_save(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        note_id = str(form.get("id", "") or "").strip()
        if not note_id:
            return JSONResponse({"success": False, "error": "ID de note manquant"}, status_code=400)

        title = str(form.get("title", "") or "").strip()
        content = str(form.get("content", "") or "")
        color = str(form.get("color", "yellow") or "yellow").strip()
        pinned = form.get("pinned") == "true" or form.get("pinned") == "1"

        note = save_user_note(note_id, title, content, color, pinned)
        return JSONResponse({"success": True, "note": note})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/notes/api/delete", name="notes_api_delete")
async def notes_api_delete(request: Request):
    if not get_current_user(request):
        return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
    await csrf_protect(request)

    try:
        form = await request.form()
        note_id = str(form.get("id", "") or "").strip()
        if not note_id:
            return JSONResponse({"success": False, "error": "ID de note manquant"}, status_code=400)

        success = delete_user_note(note_id)
        return JSONResponse({"success": success})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/sw.js", name="service_worker")
async def service_worker():
    from app.version import APP_VERSION
    from fastapi import Response
    sw_path = paths.static_dir / "sw.js"
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if sw_path.exists():
        try:
            with open(sw_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Remplace la version statique par la version dynamique de l'application
            content = content.replace(
                'const VERSION = "fabouanes-v47-offline";',
                f'const VERSION = "fabouanes-{APP_VERSION}-offline";'
            )
            return Response(content, media_type="application/javascript", headers=headers)
        except Exception as e:
            logger.warning("Erreur lors de l'injection de version dans sw.js: %s", e)
    return FileResponse(sw_path, media_type="application/javascript", headers=headers)


@router.get("/pdf-reader", name="pdf_reader")
@router.get("/bons", name="bons_space")
async def pdf_reader(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    q = str(request.query_params.get("q", "") or "").strip()
    kind = str(request.query_params.get("kind", "") or "").strip()
    selected_key = str(request.query_params.get("doc", "") or "").strip()
    legacy_file = str(request.query_params.get("file", "") or "").strip()
    if legacy_file and not selected_key:
        selected_key = f"pdf:{legacy_file}"
    documents = await list_bon_space_documents(q=q, kind=kind)
    selected = find_bon_space_document(documents, selected_key)
    missing_doc_key = selected_key if selected_key and selected is None else ""
    return templates.TemplateResponse(
        "pdf_reader.html",
        template_context(
            request,
            files=list_pdf_reader_files(),
            documents=documents,
            selected_doc=selected,
            missing_doc_key=missing_doc_key,
            filters={"q": q, "kind": kind},
        ),
    )


@router.post("/pdf-reader", name="pdf_reader")
@router.post("/bons", name="bons_space")
async def pdf_reader_submit(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    await csrf_protect(request)
    form = await request.form()
    action = str(form.get("action", "upload") or "upload").strip()
    if action == "delete":
        filename = str(form.get("filename", "") or "").strip()
        if filename and delete_pdf_reader_file(filename):
            flash(request, f"PDF supprimé : {filename}", "success")
        else:
            flash(request, "Fichier introuvable.", "warning")
        return RedirectResponse("/bons", status_code=303)
    uploaded = form.get("pdf_file")
    if not uploaded or not getattr(uploaded, "filename", ""):
        flash(request, "Choisissez un fichier PDF.", "warning")
        return RedirectResponse("/bons", status_code=303)
    try:
        filename = save_pdf_reader_upload(uploaded)
    except ValueError as exc:
        flash(request, str(exc), "danger" if "acceptes" in str(exc) else "warning")
        return RedirectResponse("/bons", status_code=303)
    flash(request, f"PDF ajouté : {filename}", "success")
    return RedirectResponse(f"/bons?doc=pdf:{filename}", status_code=303)


@router.get("/pdf-reader/file/{filename:path}", name="pdf_reader_file")
@router.get("/bons/file/{filename:path}", name="bons_pdf_file")
async def pdf_reader_file(request: Request, filename: str):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    path = get_pdf_reader_file_path(filename)
    if not path:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, media_type="application/pdf")


@router.get("/health", name="health")
async def health():
    return JSONResponse({"ok": True, "service": "FABOuanes", "version": VERSION_LABEL, "pool": postgres_pool_status()})
