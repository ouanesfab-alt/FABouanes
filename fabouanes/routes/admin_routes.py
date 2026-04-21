from __future__ import annotations

from flask import flash, make_response, redirect, render_template, request, url_for

from fabouanes.core.audit import export_audit_logs_csv
from fabouanes.core.decorators import admin_required
from fabouanes.core.permissions import PERMISSION_AUDIT_READ, require_permission
from fabouanes.routes.route_utils import bind_route
from fabouanes.services.admin_service import (
    create_manual_backup,
    create_user_account,
    get_admin_view_data,
    restore_backup_by_value,
    save_backup_settings_from_form,
    update_user_account,
)


def register_admin_routes(app):
    @admin_required
    def admin_panel():
        if request.method == "POST":
            action = request.form.get("action", "create_user")
            if action == "create_user":
                result = create_user_account(
                    request.form.get("username", ""),
                    request.form.get("password", ""),
                    request.form.get("role", "operator"),
                )
            elif action == "update_user":
                result = update_user_account(
                    int(request.form.get("user_id", "0") or 0),
                    request.form.get("role", "operator"),
                    request.form.get("is_active") == "1",
                )
            elif action == "save_backup_settings":
                result = save_backup_settings_from_form(dict(request.form))
            elif action == "backup_now":
                result = create_manual_backup()
            elif action == "restore_backup":
                result = restore_backup_by_value(request.form.get("backup_name", ""))
            else:
                result = {"ok": False, "message": "Action inconnue."}
            flash(result["message"], "success" if result["ok"] else "danger")
            return redirect(url_for("admin_panel"))

        context = get_admin_view_data(dict(request.args))
        return render_template("admin.html", **context)

    @admin_required
    def users():
        return redirect(url_for("admin_panel"))

    @require_permission(PERMISSION_AUDIT_READ)
    def admin_audit_page():
        context = get_admin_view_data(dict(request.args))
        return render_template("admin.html", focus_section="audit", **context)

    @require_permission(PERMISSION_AUDIT_READ)
    def admin_audit_export():
        payload = export_audit_logs_csv(dict(request.args), limit=1000)
        response = make_response(payload)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = "attachment; filename=audit_logs.csv"
        return response

    bind_route(app, "/admin", "admin_panel", admin_panel, ["GET", "POST"])
    bind_route(app, "/users", "users", users, ["GET"])
    bind_route(app, "/admin/audit", "admin_audit_page", admin_audit_page, ["GET"])
    bind_route(app, "/admin/audit/export", "admin_audit_export", admin_audit_export, ["GET"])
