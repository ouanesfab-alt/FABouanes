from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.web.deps import csrf_protect, flash, require_permission, template_context, templates
from app.core.audit import export_audit_logs_csv
from app.core.permissions import PERMISSION_AUDIT_READ, PERMISSION_SETTINGS_MANAGE, PERMISSION_USERS_MANAGE
from app.services.admin_service import (
    create_manual_backup,
    create_user_account,
    get_admin_view_data,
    restore_backup_by_value,
    run_database_maintenance,
    save_backup_settings_from_form,
    update_user_account,
)
from app.services.system_service import export_diagnostic_report, get_system_status


router = APIRouter()


@router.get("/admin", name="admin_panel")
async def admin_panel_page(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied
    context = get_admin_view_data(dict(request.query_params))
    return templates.TemplateResponse("admin.html", template_context(request, **context))


@router.post("/admin", name="admin_panel")
async def admin_panel_submit(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    action = form.get("action", "create_user")
    if action == "create_user":
        result = create_user_account(form.get("username", ""), form.get("password", ""), form.get("role", "operator"))
    elif action == "update_user":
        result = update_user_account(
            int(form.get("user_id", "0") or 0),
            form.get("role", "operator"),
            form.get("is_active") == "1",
            form.get("new_password", ""),
        )
    elif action == "save_backup_settings":
        result = save_backup_settings_from_form(dict(form))
    elif action == "backup_now":
        result = create_manual_backup()
    elif action == "restore_backup":
        result = restore_backup_by_value(form.get("backup_name", ""))
    elif action == "database_maintenance":
        result = run_database_maintenance()
    else:
        result = {"ok": False, "message": "Action inconnue."}
    flash(request, result["message"], "success" if result["ok"] else "danger")
    return RedirectResponse("/admin", status_code=303)


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
    context = get_admin_view_data(dict(request.query_params))
    return templates.TemplateResponse("admin.html", template_context(request, focus_section="audit", **context))


@router.get("/admin/audit/export", name="admin_audit_export")
async def admin_audit_export(request: Request):
    denied = require_permission(request, PERMISSION_AUDIT_READ)
    if denied:
        return denied
    payload = export_audit_logs_csv(dict(request.query_params), limit=1000)
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
    return templates.TemplateResponse("system_status.html", template_context(request, system_status=get_system_status()))


@router.get("/admin/system-status/export", name="admin_system_status_export")
async def admin_system_status_export(request: Request):
    denied = require_permission(request, PERMISSION_SETTINGS_MANAGE)
    if denied:
        return denied
    return Response(
        content=export_diagnostic_report(),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=diagnostic_report.json"},
    )
