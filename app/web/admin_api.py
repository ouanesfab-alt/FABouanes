# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any
from fastapi import APIRouter, Request, HTTPException, status

from app.web.deps import get_current_user
from app.core.permissions import (
    has_permission,
    PERMISSION_SETTINGS_MANAGE,
    PERMISSION_USERS_MANAGE,
    PERMISSION_AUDIT_READ,
)
from app.services.admin_service import (
    create_user_account,
    update_user_account,
    delete_user_account,
    create_manual_backup,
    restore_backup_by_value,
    save_backup_settings_from_form,
    run_database_maintenance,
)
from app.core.db_helpers import db_manager
from app.core.async_db import get_async_sessionmaker
from app.modules.users.repository import list_users
from app.core.storage import list_restore_backups
from app.services.backup_service import list_backup_jobs
from app.services.system_service import get_system_status

router = APIRouter(prefix="/api/admin", tags=["admin-api"])


def enforce_permission(request: Request, permission: str) -> dict[str, Any]:
    """S'assure que l'utilisateur est authentifié et possède la permission requise."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée ou non authentifiée."
        )
    if not has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : privilèges insuffisants."
        )
    return user


# ==========================================
# GESTION DES UTILISATEURS
# ==========================================

@router.get("/users")
async def api_get_users(request: Request):
    enforce_permission(request, PERMISSION_USERS_MANAGE)
    async with get_async_sessionmaker()() as session:
        users = await list_users(db=session)
    return {"ok": True, "users": [dict(u) for u in users]}


@router.post("/users")
async def api_create_user(request: Request):
    enforce_permission(request, PERMISSION_USERS_MANAGE)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corps de requête JSON invalide.")

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "operator").strip()

    if not username or not password:
        return {"ok": False, "message": "Nom d'utilisateur et mot de passe requis."}

    async with get_async_sessionmaker()() as session:
        result = await create_user_account(username, password, role, db=session)
        if result.get("ok"):
            await session.commit()
    return result


@router.put("/users/{user_id}")
async def api_update_user(request: Request, user_id: int):
    enforce_permission(request, PERMISSION_USERS_MANAGE)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corps de requête JSON invalide.")

    role = data.get("role", "operator").strip()
    is_active = bool(data.get("is_active", True))
    new_password = data.get("new_password", "").strip()

    async with get_async_sessionmaker()() as session:
        result = await update_user_account(user_id, role, is_active, new_password, db=session)
        if result.get("ok"):
            await session.commit()
    return result


@router.delete("/users/{user_id}")
async def api_delete_user(request: Request, user_id: int):
    current_user = enforce_permission(request, PERMISSION_USERS_MANAGE)

    # Empêcher la suppression de son propre compte
    if current_user.get("id") == user_id:
        return {"ok": False, "message": "Vous ne pouvez pas supprimer votre propre compte en cours d'utilisation."}

    async with get_async_sessionmaker()() as session:
        result = await delete_user_account(user_id, db=session)
        if result.get("ok"):
            await session.commit()
    return result


# ==========================================
# SAUVEGARDES & RESTAURATION
# ==========================================

@router.get("/backups")
async def api_get_backups(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)

    # Récupérer les sauvegardes locales
    backups = await asyncio.to_thread(list_restore_backups)

    # Récupérer l'historique des jobs
    async with get_async_sessionmaker()() as session:
        jobs = await list_backup_jobs(limit=30, db=session)
        from app.services.backup_service import get_backup_settings
        settings = await get_backup_settings(db=session)

    return {
        "ok": True,
        "backups": list(backups),
        "jobs": jobs,
        "settings": {
            "gdrive_backup_dir": settings.get("gdrive_backup_dir") or "",
            "pg_dump_path": settings.get("pg_dump_path") or "",
            "backup_snapshot_time": settings.get("backup_snapshot_time") or "02:00",
            "backup_local_retention": settings.get("backup_local_retention") or 30,
            "backup_event_retention": settings.get("backup_event_retention") or 100
        }
    }


@router.post("/backups")
async def api_trigger_backup(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)
    async with get_async_sessionmaker()() as session:
        result = await create_manual_backup(db=session)
        if result.get("ok"):
            await session.commit()
    return result


@router.put("/backups/restore")
async def api_restore_backup(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corps de requête JSON invalide.")

    backup_name = data.get("backup_name", "").strip()
    if not backup_name:
        return {"ok": False, "message": "Nom du fichier de sauvegarde requis."}

    result = await restore_backup_by_value(backup_name)
    return result


@router.patch("/backups/settings")
async def api_save_backup_settings(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corps de requête JSON invalide.")

    async with get_async_sessionmaker()() as session:
        result = await save_backup_settings_from_form(data, db=session)
        if result.get("ok"):
            await session.commit()
    return result


# ==========================================
# JOURNAUX & AUDIT
# ==========================================

@router.get("/audit")
async def api_get_audit_logs(request: Request):
    enforce_permission(request, PERMISSION_AUDIT_READ)
    query_params = dict(request.query_params)

    # Récupérer les données avec filtrage
    async with get_async_sessionmaker()() as session:
        data = await _get_filtered_audit_data(query_params, session)

    return {
        "ok": True,
        "audit_logs": data["audit_logs"],
        "activity_logs": data["activity_logs"],
        "filters": data["filters"]
    }


async def _get_filtered_audit_data(filters: dict[str, str], db) -> dict[str, Any]:
    from app.core.audit import list_audit_logs
    from app.services.activity_service import list_admin_activity, activity_filter_values

    audit_logs = await list_audit_logs(filters, limit=150, db=db)
    activity_logs = await list_admin_activity(filters, limit=150, db=db)

    return {
        "audit_logs": audit_logs,
        "activity_logs": activity_logs,
        "filters": activity_filter_values(filters)
    }



@router.patch("/sabrina/settings")
async def api_save_sabrina_settings(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corps de requête JSON invalide.")

    api_key = data.get("gemini_api_key", "").strip()
    selected_model = data.get("gemini_model", "").strip()
    chat_mode = data.get("chat_mode", "").strip()

    if chat_mode == "local":
        db_manager.set_setting("gemini_model", "local")
    else:
        if selected_model:
            db_manager.set_setting("gemini_model", selected_model)
    if api_key:
        if not api_key.startswith("••••"):
            from app.core.security import encrypt_val
            from app.modules.assistant.schema_context import get_encryption_key
            encrypted_key = encrypt_val(api_key, get_encryption_key())
            db_manager.set_setting("gemini_api_key", encrypted_key)

    return {"ok": True, "message": "Paramètres de Sabrina enregistrés avec succès."}


# ==========================================
# SYSTÈME & MAINTENANCE
# ==========================================

@router.get("/system")
async def api_get_system_status(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)

    async with get_async_sessionmaker()() as session:
        status_info = await get_system_status(db=session)
        # Récupérer aussi les logs d'erreurs et de performance
        from sqlalchemy import text

        error_res = await session.execute(text("SELECT * FROM error_logs ORDER BY id DESC LIMIT 30"))
        error_logs = [dict(row._mapping) for row in error_res.all()]

        perf_res = await session.execute(text("SELECT * FROM performance_logs ORDER BY id DESC LIMIT 40"))
        perf_logs = [dict(row._mapping) for row in perf_res.all()]

        sys_res = await session.execute(text("SELECT * FROM system_logs ORDER BY id DESC LIMIT 20"))
        sys_logs = [dict(row._mapping) for row in sys_res.all()]

    return {
        "ok": True,
        "status": status_info,
        "error_logs": error_logs,
        "performance_logs": perf_logs,
        "system_logs": sys_logs
    }


@router.post("/maintenance")
async def api_run_maintenance(request: Request):
    enforce_permission(request, PERMISSION_SETTINGS_MANAGE)
    result = run_database_maintenance()
    return result
