from __future__ import annotations

from werkzeug.security import generate_password_hash

from app.core.activity import log_activity
from app.core.audit import audit_event, list_audit_logs
from app.core.config import APP_DATA_DIR, DEFAULT_ADMIN_USERNAME
from app.core.db_access import query_db
from app.core.perf_cache import cached_result
from app.core.security import validate_password_strength
from app.core.storage import backup_database, list_restore_backups, mark_backup_needed, resolve_backup_path, restore_database_from
from app.repositories.user_repository import (
    create_user,
    get_user_by_id,
    list_users,
    update_password,
    update_user_role_and_status,
    user_exists,
)
from app.services.auth_service import validate_new_user_payload
from app.services.backup_service import (
    enqueue_backup_snapshot,
    get_backup_settings,
    list_backup_jobs,
    run_pending_backup_jobs,
    save_backup_configuration,
)
from app.services.activity_service import activity_filter_values, list_activity_actions, list_activity_entity_types, list_admin_activity
from app.services.system_service import get_system_status


def create_user_account(username: str, password: str, role: str):
    payload = validate_new_user_payload(username, password, role)
    if not payload["ok"]:
        return payload
    username = payload["username"]
    role_value = payload["role"]
    if user_exists(username):
        return {"ok": False, "message": "Ce nom d'utilisateur existe deja."}
    user_id = create_user(username, generate_password_hash(password), role_value, 0, 1)
    created_user = get_user_by_id(user_id)
    log_activity("create_user", "user", user_id, f"Creation du compte {username}")
    audit_event("create_user", "user", user_id, after=created_user)
    try:
        mark_backup_needed("create_user")
    except Exception:
        pass
    return {"ok": True, "message": "Compte créé avec succès."}


def update_user_account(user_id: int, role: str, is_active: bool, new_password: str = ""):
    user = get_user_by_id(user_id)
    if not user:
        return {"ok": False, "message": "Utilisateur introuvable."}
    password = str(new_password or "").strip()
    password_changed = bool(password)
    if password_changed:
        ok, password_msg = validate_password_strength(password)
        if not ok:
            return {"ok": False, "message": password_msg}
    before = dict(user)
    update_user_role_and_status(user_id, role, int(bool(is_active)))
    if password_changed:
        update_password(user_id, generate_password_hash(password), 0)
        if str(user["username"]) == DEFAULT_ADMIN_USERNAME:
            try:
                (APP_DATA_DIR / "first_admin_password.txt").unlink(missing_ok=True)
            except Exception:
                pass
    updated = get_user_by_id(user_id)
    detail = f"Role={updated['role']} actif={updated['is_active']}"
    if password_changed:
        detail += " mot_de_passe=modifie"
    log_activity("update_user", "user", user_id, detail)
    audit_event("update_user", "user", user_id, before=before, after=updated)
    try:
        mark_backup_needed("update_user_password" if password_changed else "update_user")
    except Exception:
        pass
    message = "Compte et mot de passe mis à jour." if password_changed else "Compte mis à jour."
    return {"ok": True, "message": message}


def save_backup_settings_from_form(form_data: dict[str, str]):
    save_backup_configuration(form_data)
    log_activity("update_backup_settings", "settings", None, "Mise à jour des paramètres de sauvegarde")
    audit_event(
        "update_backup_settings",
        "settings",
        "backup",
        after={
            "gdrive_backup_dir": form_data.get("gdrive_backup_dir", ""),
            "backup_snapshot_time": form_data.get("backup_snapshot_time", "02:00"),
            "backup_local_retention": form_data.get("backup_local_retention", "30"),
            "backup_event_retention": form_data.get("backup_event_retention", "100"),
        },
    )
    return {"ok": True, "message": "Paramètres de sauvegarde enregistrés."}


def create_manual_backup():
    job_id = enqueue_backup_snapshot("manual", "manual")
    log_activity("backup_now", "backup", job_id, "Sauvegarde mise en file d'attente")
    audit_event("backup_now", "backup", str(job_id), after={"job_id": job_id, "status": "pending"})
    return {"ok": True, "message": f"Sauvegarde lancee en arriere-plan (job #{job_id})."}


def restore_backup_by_value(backup_value: str):
    backup_path = resolve_backup_path((backup_value or "").strip())
    if backup_path is None or not backup_path.exists():
        return {"ok": False, "message": "Sauvegarde introuvable."}
    try:
        backup_database("before_restore", backup_type="manual")
        restore_database_from(str(backup_path))
    except Exception as exc:
        audit_event("restore_backup", "backup", str(backup_value or "").strip(), status="failure", meta={"reason": str(exc)})
        return {"ok": False, "message": f"Restauration impossible: {exc}"}
    log_activity("restore_backup", "backup", None, backup_path.name)
    audit_event("restore_backup", "backup", backup_path.name, after={"filename": backup_path.name})
    return {"ok": True, "message": "Restauration effectuée."}


def run_database_maintenance():
    # PostgreSQL auto-vacuums, no manual maintenance required
    return {"ok": True, "message": "Maintenance terminée (automatisée par PostgreSQL)."}


def _build_restore_list():
    return list(list_restore_backups())


def get_admin_view_data(audit_filters: dict[str, str] | None = None):
    normalized_filters = audit_filters or {}
    filter_key = tuple(sorted(normalized_filters.items()))
    return cached_result(
        ("admin_view_data", filter_key),
        lambda: _build_admin_view_data(normalized_filters),
        ttl_seconds=30.0,
    )


def _build_admin_view_data(audit_filters: dict[str, str]):
    backup_jobs = list_backup_jobs(limit=20)
    latest_backup_error = next((job for job in backup_jobs if (job["error_message"] or "").strip()), None)
    activity_logs = list_admin_activity(audit_filters, limit=80)
    return {
        "users": list_users(),
        "backups": _build_restore_list(),
        "backup_jobs": backup_jobs,
        "recent_logins": query_db("SELECT * FROM activity_logs WHERE action IN ('login','logout') ORDER BY id DESC LIMIT 20"),
        "activity_logs": activity_logs,
        "activity_filters": activity_filter_values(audit_filters),
        "activity_actions": list_activity_actions(),
        "activity_entity_types": list_activity_entity_types(),
        "error_logs": query_db("SELECT * FROM error_logs ORDER BY id DESC LIMIT 30"),
        "system_logs": query_db("SELECT * FROM system_logs ORDER BY id DESC LIMIT 20"),
        "performance_logs": query_db("SELECT * FROM performance_logs ORDER BY id DESC LIMIT 40"),
        "audit_logs": list_audit_logs(audit_filters, limit=120),
        "audit_filters": audit_filters,
        "settings": get_backup_settings(),
        "latest_backup_error": latest_backup_error,
        "system_status": get_system_status(),
        "stock_movements": query_db("SELECT * FROM stock_movements ORDER BY id DESC LIMIT 20"),
    }
