from __future__ import annotations

import asyncio
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat

from app.core.activity import log_activity
from app.core.audit import audit_event, list_audit_logs
from app.core.config import APP_DATA_DIR, DEFAULT_ADMIN_USERNAME
from app.core.perf_cache import async_cached_result
from app.core.security import validate_password_strength
from app.core.storage import backup_database, list_restore_backups, mark_backup_needed, resolve_backup_path, restore_database_from
from app.modules.users.repository import (
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
    save_backup_configuration,
)
from app.services.activity_service import activity_filter_values, list_activity_actions, list_activity_entity_types, list_admin_activity
from app.services.system_service import get_system_status


@async_compat
async def create_user_account(username: str, password: str, role: str, db: AsyncSession | None = None):
    payload = validate_new_user_payload(username, password, role)
    if not payload["ok"]:
        return payload
    username = payload["username"]
    role_value = payload["role"]
    if await user_exists(username, db=db):
        return {"ok": False, "message": "Ce nom d'utilisateur existe deja."}
    user_id = await create_user(username, generate_password_hash(password), role_value, False, True, db=db)
    created_user = await get_user_by_id(user_id, db=db)
    log_activity("create_user", "user", user_id, f"Creation du compte {username}")
    audit_event("create_user", "user", user_id, after=created_user)
    try:
        mark_backup_needed("create_user")
    except Exception:
        pass
    return {"ok": True, "message": "Compte créé avec succès."}


@async_compat
async def update_user_account(user_id: int, role: str, is_active: bool, new_password: str = "", db: AsyncSession | None = None):
    user = await get_user_by_id(user_id, db=db)
    if not user:
        return {"ok": False, "message": "Utilisateur introuvable."}
    password = str(new_password or "").strip()
    password_changed = bool(password)
    if password_changed:
        ok, password_msg = validate_password_strength(password)
        if not ok:
            return {"ok": False, "message": password_msg}
    before = dict(user)
    await update_user_role_and_status(user_id, role, bool(is_active), db=db)
    if password_changed:
        await update_password(user_id, generate_password_hash(password), False, db=db)
        if str(user["username"]) == DEFAULT_ADMIN_USERNAME:
            try:
                (APP_DATA_DIR / "first_admin_password.txt").unlink(missing_ok=True)
            except Exception:
                pass
    updated = await get_user_by_id(user_id, db=db)
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


async def delete_user_account(user_id: int, db: AsyncSession | None = None):
    # Récupérer l'utilisateur pour les logs
    user = await get_user_by_id(user_id, db=db)
    if not user:
        return {"ok": False, "message": "Utilisateur introuvable."}

    if str(user["username"]) == DEFAULT_ADMIN_USERNAME:
        return {"ok": False, "message": "Le compte administrateur par défaut ne peut pas être supprimé."}

    from sqlalchemy.exc import IntegrityError
    from app.modules.users.repository import delete_user

    try:
        before = dict(user)
        # Tenter la suppression dans le repository
        deleted = await delete_user(user_id, db=db)
        if deleted:
            log_activity("delete_user", "user", user_id, f"Username={user['username']}")
            audit_event("delete_user", "user", user_id, before=before, after=None)
            try:
                mark_backup_needed("delete_user")
            except Exception:
                pass
            return {"ok": True, "message": "Utilisateur supprimé avec succès."}
        else:
            return {"ok": False, "message": "Erreur lors de la suppression de l'utilisateur."}
    except IntegrityError:
        # En cas d'erreur de clé étrangère
        if db is not None:
            await db.rollback()
        return {
            "ok": False,
            "message": "Cet utilisateur a des opérations comptables ou d'audit liées (ventes, achats, recettes, etc.) et ne peut pas être supprimé physiquement. Veuillez le désactiver à la place."
        }


@async_compat
async def save_backup_settings_from_form(form_data: dict[str, str], db: AsyncSession | None = None):
    await save_backup_configuration(form_data, db=db)
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
            "pg_dump_path": form_data.get("pg_dump_path", ""),
        },
    )
    return {"ok": True, "message": "Paramètres de sauvegarde enregistrés."}


@async_compat
async def create_manual_backup(db: AsyncSession | None = None):
    job_id = await enqueue_backup_snapshot("manual", "manual", db=db)
    log_activity("backup_now", "backup", job_id, "Sauvegarde mise en file d'attente")
    audit_event("backup_now", "backup", str(job_id), after={"job_id": job_id, "status": "pending"})
    return {"ok": True, "message": f"Sauvegarde lancee en arriere-plan (job #{job_id})."}


@async_compat
async def restore_backup_by_value(backup_value: str):
    backup_path = resolve_backup_path((backup_value or "").strip())
    if backup_path is None or not backup_path.exists():
        return {"ok": False, "message": "Sauvegarde introuvable."}
    try:
        await asyncio.to_thread(backup_database, "before_restore", backup_type="manual")
        await asyncio.to_thread(restore_database_from, str(backup_path))
    except Exception as exc:
        audit_event("restore_backup", "backup", str(backup_value or "").strip(), status="failure", meta={"reason": str(exc)})
        return {"ok": False, "message": f"Restauration impossible: {exc}"}
    log_activity("restore_backup", "backup", None, backup_path.name)
    audit_event("restore_backup", "backup", backup_path.name, after={"filename": backup_path.name})
    return {"ok": True, "message": "Restauration effectuée."}


def run_database_maintenance():
    from app.core.db_helpers import execute_db, query_db
    try:
        query_db("PRAGMA optimize")
        execute_db("VACUUM")
        return {"ok": True, "message": "Maintenance SQLite (VACUUM & PRAGMA optimize) effectuée avec succès."}
    except Exception as exc:
        return {"ok": False, "message": f"Erreur lors de la maintenance : {exc}"}


def _build_restore_list():
    return list(list_restore_backups())


@async_compat
async def get_admin_view_data(audit_filters: dict[str, str] | None = None, db: AsyncSession | None = None):
    normalized_filters = audit_filters or {}
    filter_key = tuple(sorted(normalized_filters.items()))

    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _build_admin_view_data(normalized_filters, session)
        return await _build_admin_view_data(normalized_filters, db)

    return await async_cached_result(
        ("admin_view_data", filter_key),
        load,
        ttl_seconds=30.0,
    )


async def _build_admin_view_data(audit_filters: dict[str, str], db: AsyncSession):
    backup_jobs = await list_backup_jobs(limit=20, db=db)
    latest_backup_error = next((job for job in backup_jobs if (job["error_message"] or "").strip()), None)
    activity_logs = await list_admin_activity(audit_filters, limit=80, db=db)

    users = await list_users(db=db)
    backups = await asyncio.to_thread(_build_restore_list)

    recent_logins_res = await db.execute(
        text("SELECT * FROM activity_logs WHERE action IN ('login','logout') ORDER BY id DESC LIMIT 20")
    )
    recent_logins = [dict(row._mapping) for row in recent_logins_res.all()]

    activity_actions = await list_activity_actions(db=db)
    activity_entity_types = await list_activity_entity_types(db=db)

    error_logs_res = await db.execute(text("SELECT * FROM error_logs ORDER BY id DESC LIMIT 30"))
    error_logs = [dict(row._mapping) for row in error_logs_res.all()]

    system_logs_res = await db.execute(text("SELECT * FROM system_logs ORDER BY id DESC LIMIT 20"))
    system_logs = [dict(row._mapping) for row in system_logs_res.all()]

    performance_logs_res = await db.execute(text("SELECT * FROM performance_logs ORDER BY id DESC LIMIT 40"))
    performance_logs = [dict(row._mapping) for row in performance_logs_res.all()]

    audit_logs = await list_audit_logs(audit_filters, limit=120, db=db)
    settings = await get_backup_settings(db=db)
    system_status = await get_system_status(db=db)

    stock_movements_res = await db.execute(text("SELECT * FROM stock_movements ORDER BY id DESC LIMIT 20"))
    stock_movements = [dict(row._mapping) for row in stock_movements_res.all()]

    from app.modules.assistant.service import is_ollama_available
    from app.modules.assistant.schema_context import get_gemini_api_key
    from app.core.db_helpers import db_manager as helper_db_manager

    sabrina_api_key = get_gemini_api_key()
    selected_model = helper_db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip() or "gemini-3.1-flash-lite"
    has_key = bool(sabrina_api_key)
    ollama_ok = await is_ollama_available()

    return {
        "users": users,
        "backups": backups,
        "backup_jobs": backup_jobs,
        "recent_logins": recent_logins,
        "activity_logs": activity_logs,
        "activity_filters": activity_filter_values(audit_filters),
        "activity_actions": activity_actions,
        "activity_entity_types": activity_entity_types,
        "error_logs": error_logs,
        "system_logs": system_logs,
        "performance_logs": performance_logs,
        "audit_logs": audit_logs,
        "audit_filters": audit_filters,
        "settings": settings,
        "latest_backup_error": latest_backup_error,
        "system_status": system_status,
        "stock_movements": stock_movements,
        "sabrina_selected_model": selected_model,
        "sabrina_has_key": has_key,
        "sabrina_ollama_ok": ollama_ok,
    }
