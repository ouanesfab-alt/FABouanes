from __future__ import annotations

import logging
from typing import Any, Dict


logger = logging.getLogger("fabouanes.assistant")


def log_structured_failure(action: str, error: str, parameters: dict):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_failures.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "error": error,
        "parameters": parameters
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write structured failure log: %s", e)


def log_sabrina_action(action: str, args: dict, confirmed: bool, success: bool, result_summary: str):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_audit.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "arguments": args,
        "confirmed": confirmed,
        "success": success,
        "result_summary": result_summary
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write sabrina audit log: %s", e)


async def execute_tool_action(func_name: str, func_args: dict, user_role: str = "operator") -> Dict[str, Any]:
    ADMIN_ONLY_TOOLS = {
        "create_app_user", "change_app_user_password", "delete_app_user",
        "create_app_backup", "list_app_backups", "restore_app_backup"
    }
    if func_name in ADMIN_ONLY_TOOLS and user_role != "admin":
        return {"error": "Sécurité : Cette action d'administration est réservée aux administrateurs."}

    from app.core.async_db import get_async_sessionmaker
    session_maker = get_async_sessionmaker()
    try:
        res = await _execute_tool_action_inner(func_name, func_args, session_maker, user_role=user_role)
        if isinstance(res, dict) and "error" in res:
            log_structured_failure(func_name, res["error"], func_args)
        else:
            summary = res.get("message") or res.get("print_url") or "Opération réussie"
            log_sabrina_action(func_name, func_args, confirmed=True, success=True, result_summary=str(summary))
        from app.modules.assistant.sql_tools import serialize_for_json
        return serialize_for_json(res)
    except Exception as e:
        logger.error("Error executing agent action %s with args %s: %s", func_name, func_args, e, exc_info=True)
        log_structured_failure(func_name, str(e), func_args)
        return {"error": str(e)}


def sanitize_numeric(val: Any) -> float:
    from app.modules.assistant.business_helpers import parse_amount
    return parse_amount(val)


# ---------------------------------------------------------------------------
# Constantes partagées
# ---------------------------------------------------------------------------

# Normalisation des catégories de dépenses (alias → valeur DB)
EXPENSE_CATEGORY_MAP: Dict[str, str] = {
    "matiere_premiere": "general", "matière première": "general", "matière": "general",
    "carburant": "transport", "essence": "transport", "gazole": "transport", "transport": "transport",
    "fournitures": "fournitures", "fournitures de bureau": "fournitures",
    "loyer": "loyer",
    "salaires": "salaires", "salaire": "salaires", "paie": "salaires",
    "maintenance": "maintenance", "reparation": "maintenance", "réparation": "maintenance",
    "telecom": "telecom", "internet": "telecom", "telephone": "telecom", "téléphone": "telecom",
    "energie": "energie", "électricité": "energie", "electricite": "energie", "eau": "energie", "gaz": "energie",
    "impots": "impots", "impôt": "impots", "taxe": "impots", "taxes": "impots",
    "autre": "autre", "divers": "autre",
}

_ALLOWED_EXPENSE_CATEGORIES = frozenset(EXPENSE_CATEGORY_MAP.values())


# ---------------------------------------------------------------------------
# Sécurité chemin fichier
# ---------------------------------------------------------------------------

def _assert_workspace_path(abs_path: str, workspace_dir: str) -> None:
    """Lève ValueError si abs_path sort du répertoire de l'application."""
    try:
        common = __import__("os").path.commonpath([workspace_dir, abs_path])
        if common != workspace_dir:
            raise ValueError()
    except Exception:
        raise ValueError("Sécurité : Accès interdit en dehors du répertoire de l'application.")


async def _execute_tool_action_inner(func_name: str, func_args: dict, session_maker, user_role: str = "operator") -> Dict[str, Any]:
    from app.modules.assistant.tool_actions_admin import handle_admin
    from app.modules.assistant.tool_actions_contacts import handle_contacts
    from app.modules.assistant.tool_actions_catalog import handle_catalog
    from app.modules.assistant.tool_actions_operations import handle_operations
    from app.modules.assistant.tool_actions_production import handle_production
    from app.modules.assistant.tool_actions_tools import handle_tools
    from app.modules.assistant.tool_actions_insights import handle_insights

    res = await handle_admin(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_contacts(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_catalog(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_operations(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_production(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_tools(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    res = await handle_insights(func_name, func_args, session_maker, user_role)
    if res is not None:
        return res

    return {"error": f"Action inconnue : {func_name}"}
