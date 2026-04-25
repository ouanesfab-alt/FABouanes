from __future__ import annotations

from werkzeug.security import generate_password_hash

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event, list_audit_logs
from fabouanes.core.db_access import query_db
from fabouanes.core.perf_cache import cached_result
from fabouanes.core.storage import backup_database, list_restore_backups, resolve_backup_path, restore_database_from
from fabouanes.repositories.user_repository import (
    create_user,
    get_user_by_id,
    list_users,
    update_user_role_and_status,
    user_exists,
)
from fabouanes.services.auth_service import validate_new_user_payload
from fabouanes.services.backup_service import (
    get_backup_settings,
    list_backup_jobs,
    run_pending_backup_jobs,
    save_backup_configuration,
)


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
        backup_database("create_user")
    except Exception:
        pass
    return {"ok": True, "message": "Compte cree avec succes."}


def update_user_account(user_id: int, role: str, is_active: bool):
    user = get_user_by_id(user_id)
    if not user:
        return {"ok": False, "message": "Utilisateur introuvable."}
    before = dict(user)
    update_user_role_and_status(user_id, role, int(bool(is_active)))
    updated = get_user_by_id(user_id)
    log_activity("update_user", "user", user_id, f"Role={updated['role']} actif={updated['is_active']}")
    audit_event("update_user", "user", user_id, before=before, after=updated)
    try:
        backup_database("update_user")
    except Exception:
        pass
    return {"ok": True, "message": "Compte mis a jour."}


def save_backup_settings_from_form(form_data: dict[str, str]):
    save_backup_configuration(form_data)
    log_activity("update_backup_settings", "settings", None, "Mise a jour des parametres de sauvegarde")
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
    return {"ok": True, "message": "Parametres de sauvegarde enregistres."}


def create_manual_backup():
    path = backup_database("manual", backup_type="manual")
    run_pending_backup_jobs(limit=1)
    log_activity("backup_now", "backup", None, str(path))
    audit_event("backup_now", "backup", path.name, after={"filename": path.name})
    return {"ok": True, "message": f"Sauvegarde creee : {path.name}"}


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
    return {"ok": True, "message": "Restauration effectuee."}


def _build_restore_list():
    return list(list_restore_backups())


def get_admin_view_data(audit_filters: dict[str, str] | None = None):
    normalized_filters = audit_filters or {}
    filter_key = tuple(sorted(normalized_filters.items()))
    return cached_result(
        ("admin_view_data", filter_key),
        lambda: _build_admin_view_data(normalized_filters),
        ttl_seconds=6.0,
    )


def _build_admin_view_data(audit_filters: dict[str, str]):
    backup_jobs = list_backup_jobs(limit=20)
    latest_backup_error = next((job for job in backup_jobs if (job["error_message"] or "").strip()), None)
    return {
        "users": list_users(),
        "backups": _build_restore_list(),
        "backup_jobs": backup_jobs,
        "recent_logins": query_db("SELECT * FROM activity_logs WHERE action IN ('login','logout') ORDER BY id DESC LIMIT 20"),
        "activity_logs": query_db("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 50"),
        "error_logs": query_db("SELECT * FROM error_logs ORDER BY id DESC LIMIT 30"),
        "system_logs": query_db("SELECT * FROM system_logs ORDER BY id DESC LIMIT 20"),
        "audit_logs": list_audit_logs(audit_filters, limit=120),
        "audit_filters": audit_filters,
        "settings": get_backup_settings(),
        "latest_backup_error": latest_backup_error,
    }
