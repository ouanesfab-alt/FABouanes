from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.web.deps import require_permission, template_context, templates
from app.core.rate_limit import limiter
from app.core.audit import export_audit_logs_csv
from app.core.permissions import PERMISSION_AUDIT_READ, PERMISSION_SETTINGS_MANAGE, PERMISSION_USERS_MANAGE
from app.services.admin_service import (
    get_admin_view_data,
)
from app.services.system_service import export_diagnostic_report, get_system_status


router = APIRouter()


@router.get("/admin", name="admin_panel")
async def admin_panel_page(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied

    from app.modules.assistant.schema_context import get_gemini_api_key
    from app.core.db_helpers import db_manager
    from app.modules.assistant.service import is_ollama_available

    sabrina_api_key = get_gemini_api_key()
    selected_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip() or "gemini-3.1-flash-lite"
    has_key = bool(sabrina_api_key)
    ollama_ok = await is_ollama_available()

    context = {
        "sabrina_selected_model": selected_model,
        "sabrina_has_key": has_key,
        "sabrina_ollama_ok": ollama_ok,
    }
    return templates.TemplateResponse("admin.html", template_context(request, **context))


@router.get("/users", name="users")
async def users_page(request: Request):
    denied = require_permission(request, PERMISSION_USERS_MANAGE)
    if denied:
        return denied
    return RedirectResponse("/admin", status_code=303)


@router.get("/admin/audit", name="admin_audit_page")
async def admin_audit_page(request: Request):
    denied = require_permission(request, PERMISSION_AUDIT_READ)
    if denied:
        return denied
    context = await get_admin_view_data(dict(request.query_params))
    return templates.TemplateResponse("admin.html", template_context(request, focus_section="audit", **context))


@router.get("/admin/audit/export", name="admin_audit_export")
@limiter.limit("10/minute")
async def admin_audit_export(request: Request):
    denied = require_permission(request, PERMISSION_AUDIT_READ)
    if denied:
        return denied
    payload = await export_audit_logs_csv(dict(request.query_params), limit=1000)
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


@router.get("/admin/system-status", name="admin_system_status")
async def admin_system_status(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied
    return templates.TemplateResponse("system_status.html", template_context(request, system_status=await get_system_status()))


@router.get("/admin/system-status/export", name="admin_system_status_export")
@limiter.limit("10/minute")
async def admin_system_status_export(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied
    return Response(
        content=await export_diagnostic_report(),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=diagnostic_report.json"},
    )




