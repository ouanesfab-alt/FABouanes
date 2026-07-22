# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import os
from typing import Any, Dict
from app.core.config import BASE_DIR
from app.core.db_helpers import db_manager
from app.modules.assistant.tool_actions import _assert_workspace_path

logger = logging.getLogger("fabouanes.assistant")

async def handle_admin(func_name: str, func_args: dict, session_maker, user_role: str = 'operator') -> Dict[str, Any] | None:

    if func_name == "read_app_file":
            filepath = func_args.get("filepath", "")
            workspace_dir = os.path.abspath(str(BASE_DIR))
            abs_path = os.path.abspath(filepath)
            try:
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
            with open(abs_path, "r", encoding="utf-8") as f:
                return {"content": f.read()}

    elif func_name == "modify_app_file":
            filepath = func_args.get("filepath", "")
            old_c = func_args.get("old_content", "")
            new_c = func_args.get("new_content", "")
            workspace_dir = os.path.abspath(str(BASE_DIR))
            abs_path = os.path.abspath(filepath)
            try:
                _assert_workspace_path(abs_path, workspace_dir)
            except ValueError as e:
                return {"error": str(e)}
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_c not in content:
                return {"error": "Le contenu original à remplacer n'a pas été trouvé dans le fichier."}
            new_content = content.replace(old_c, new_c, 1)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"success": True, "message": "Fichier modifié avec succès."}

    elif func_name == "create_app_backup":
            from app.services.admin_service import create_manual_backup
            res = await create_manual_backup()
            return {"success": True, "backup": res}

    elif func_name == "list_app_backups":
            from app.services.admin_service import list_restore_backups
            res = list_restore_backups()
            return {"backups": res}

    elif func_name == "restore_app_backup":
            backup_name = func_args.get("backup_name", "")
            from app.services.admin_service import restore_backup_by_value
            await restore_backup_by_value(backup_name)
            return {"success": True, "message": "Restauration effectuée avec succès."}

    elif func_name == "create_app_user":
            username = func_args.get("username", "")
            password = func_args.get("password", "")
            role = func_args.get("role", "operator")
            from app.services.admin_service import create_user_account
            res = await create_user_account(username, password, role)
            if not res.get("ok"):
                return {"error": res.get("message", "Creation utilisateur refusee.")}
            return {"success": True, "message": res.get("message", f"Utilisateur {username} cree.")}

    elif func_name == "change_app_user_password":
            username = func_args.get("username", "")
            new_password = func_args.get("new_password", "")
            from app.core.security import validate_password_strength
            from app.services.auth_service import get_user_by_username, generate_password_hash
            from app.modules.users.repository import update_password
            ok, password_msg = validate_password_strength(new_password)
            if not ok:
                return {"error": password_msg}
            user = await get_user_by_username(username)
            if not user:
                return {"error": f"Utilisateur {username} introuvable."}
            async with session_maker() as session:
                await update_password(user["id"], generate_password_hash(new_password), 0, db=session)
                await session.commit()
            return {"success": True, "message": f"Mot de passe de {username} modifié."}

    elif func_name == "delete_app_user":
            username = func_args.get("username", "")
            from app.services.auth_service import get_user_by_username
            user = await get_user_by_username(username)
            if not user:
                return {"error": f"Utilisateur {username} introuvable."}
            async with session_maker() as session:
                from sqlmodel import text
                await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user["id"]})
                await session.commit()
            return {"success": True, "message": f"Utilisateur {username} supprimé."}

    elif func_name == "update_app_user":
            from app.services.admin_service import update_user_account
            user_id = int(func_args.get("user_id") or 0)
            role = func_args.get("role", "").strip()
            is_active = bool(func_args.get("is_active"))
            new_password = func_args.get("new_password", "").strip()

            await update_user_account(
                user_id=user_id,
                role=role,
                is_active=is_active,
                new_password=new_password
            )
            return {"success": True, "message": f"Utilisateur #{user_id} mis à jour avec succès."}

    elif func_name == "update_setting":
            key = func_args.get("key", "")
            value = func_args.get("value", "")
            db_manager.set_setting(key, value)
            return {"success": True, "message": f"Paramètre {key} mis à jour."}

    elif func_name == "run_system_maintenance":
            from app.services.admin_service import run_database_maintenance
            result = run_database_maintenance()
            return {"success": result.get("ok", False), "message": result.get("message", "Maintenance complétée.")}

    elif func_name == "save_backup_settings":
            from app.services.backup_service import save_backup_configuration
            payload = {
                "gdrive_backup_dir": func_args.get("gdrive_backup_dir", ""),
                "backup_snapshot_time": func_args.get("backup_snapshot_time", "02:00"),
                "backup_local_retention": func_args.get("backup_local_retention", 30),
                "backup_event_retention": func_args.get("backup_event_retention", 100),
            }
            await save_backup_configuration(payload)
            return {"success": True, "message": "Configuration des sauvegardes enregistrée avec succès."}

    return None
