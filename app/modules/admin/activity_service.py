from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker
from app.core.config import APP_DATA_DIR
from app.core.database import execute_db
from app.core.request_state import get_state_value
from app.infra.perf_cache import async_cached_result

logger = logging.getLogger("fabouanes.activity")
LOG_DIR = APP_DATA_DIR / "logs"


def write_text_log(filename: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOG_DIR / filename).open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def _current_user():
    return get_state_value("user")


def safe_username() -> str:
    try:
        user = _current_user()
        if user:
            return user["username"]
    except Exception:
        pass
    return "system"


def _request_ip() -> str:
    state_request = get_state_value("request")
    if state_request is None:
        return ""
    from app.core.security import client_ip

    return client_ip(state_request)


def _json_or_text(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def log_activity(
    action: str,
    entity_type: str = "",
    entity_id: int | None = None,
    details: str = "",
    *,
    old_value=None,
    new_value=None,
) -> None:
    username = safe_username()
    user_id = None
    try:
        user = _current_user()
        if user:
            user_id = int(user["id"])
    except Exception:
        user_id = None
    try:
        execute_db(
            """
            INSERT INTO activity_logs (
                user_id, username, action, entity_type, entity_id, details,
                old_value, new_value, ip_address, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                username,
                action,
                entity_type,
                entity_id,
                details,
                _json_or_text(old_value),
                _json_or_text(new_value),
                _request_ip(),
            ),
        )
    except Exception as exc:
        logger.warning("log_activity DB write failed: %s", exc)
    write_text_log("activity.log", f"{username} | {action} | {entity_type}#{entity_id or '-'} | {details}")


def log_error(exc: Exception, route: str = "") -> None:
    username = safe_username()
    tb = traceback.format_exc()
    current_route = route
    state_request = get_state_value("request")
    if not current_route and state_request is not None:
        current_route = state_request.url.path
    execute_db(
        """
        INSERT INTO error_logs (username, route, error_type, message, traceback, created_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (username, current_route, type(exc).__name__, str(exc), tb),
    )
    write_text_log("errors.log", f"{username} | {current_route} | {type(exc).__name__}: {exc}\n{tb}")

ACTION_LABELS = {
    "backup_now": "a créé une sauvegarde",
    "change_password": "a changé un mot de passe",
    "create_client": "a créé un client",
    "create_payment": "a enregistré un paiement",
    "create_production": "a créé une production",
    "create_purchase": "a créé un achat",
    "create_purchase_document": "a créé un bon d'achat",
    "create_sale": "a créé une vente",
    "create_sale_document": "a créé une facture",
    "create_supplier": "a créé un fournisseur",
    "create_user": "a créé un utilisateur",
    "delete_payment": "a supprimé un paiement",
    "delete_production": "a supprimé une production",
    "delete_purchase": "a supprimé un achat",
    "delete_sale": "a supprimé une vente",
    "edit_production_notes": "a modifié une production",
    "import_clients_excel": "a importé des clients Excel",
    "login": "s'est connecté",
    "logout": "s'est déconnecté",
    "restore_backup": "a restauré une sauvegarde",
    "update_backup_settings": "a modifié les sauvegardes",
    "update_client": "a modifié un client",
    "update_payment": "a modifié un paiement",
    "update_price": "a modifié un prix",
    "update_production": "a modifié une production",
    "update_purchase": "a modifié un achat",
    "update_purchase_document": "a modifié un bon d'achat",
    "update_sale": "a modifié une vente",
    "update_sale_document": "a modifié une facture",
    "update_supplier": "a modifié un fournisseur",
    "update_user": "a modifié un utilisateur",
}

ENTITY_LABELS = {
    "backup": "sauvegarde",
    "client": "client",
    "client_import": "import clients",
    "finished_product": "produit final",
    "payment": "paiement",
    "production": "production",
    "purchase": "achat",
    "purchase_document": "bon d'achat",
    "raw_material": "matière première",
    "sale": "vente",
    "sale_document": "facture",
    "settings": "paramètres",
    "supplier": "fournisseur",
    "user": "utilisateur",
}


def _display_date(value) -> str:
    from app.core.model_utils import to_gmt1

    value = to_gmt1(value)
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M")
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw[:19], fmt)
            parsed = to_gmt1(parsed)
            return parsed.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return raw[:16]


def _activity_label(action: str) -> str:
    return ACTION_LABELS.get(str(action or ""), str(action or "action"))


def _target_label(entity_type: str | None, entity_id) -> str:
    label = ENTITY_LABELS.get(str(entity_type or ""), str(entity_type or "").replace("_", " "))
    if not label:
        return "-"
    return f"{label} #{entity_id}" if entity_id not in (None, "") else label


def _decorate_activity(row) -> dict:
    item = dict(row)
    display_date = _display_date(item.get("created_at"))
    username = str(item.get("username") or "system")
    action_label = _activity_label(str(item.get("action") or ""))
    target_label = _target_label(item.get("entity_type"), item.get("entity_id"))
    details = str(item.get("details") or "").strip()
    sentence = f"{display_date} - {username} {action_label}"
    if target_label != "-":
        sentence += f" ({target_label})"
    if details:
        sentence += f" - {details}"
    item.update(
        {
            "display_date": display_date,
            "action_label": action_label,
            "target_label": target_label,
            "sentence": sentence,
        }
    )
    return item


def _filters(filters: Mapping[str, str] | None) -> dict[str, str]:
    raw = filters or {}
    return {
        "activity_q": str(raw.get("activity_q", "") or "").strip(),
        "activity_user": str(raw.get("activity_user", "") or "").strip(),
        "activity_action": str(raw.get("activity_action", "") or "").strip(),
        "activity_date": str(raw.get("activity_date", "") or "").strip(),
        "activity_type": str(raw.get("activity_type", "") or "").strip(),
    }


async def list_admin_activity(
    filters: Mapping[str, str] | None = None,
    *,
    limit: int = 80,
    db: AsyncSession | None = None,
) -> list[dict]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_admin_activity_impl(filters, limit, session)
    return await _list_admin_activity_impl(filters, limit, db)


async def _list_admin_activity_impl(
    filters: Mapping[str, str] | None,
    limit: int,
    db: AsyncSession,
) -> list[dict]:
    normalized = _filters(filters)
    where: list[str] = []
    params: dict[str, Any] = {}

    if normalized["activity_user"]:
        where.append("LOWER(username) LIKE LOWER(:activity_user)")
        params["activity_user"] = f"%{normalized['activity_user']}%"
    if normalized["activity_action"]:
        where.append("LOWER(action) = LOWER(:activity_action)")
        params["activity_action"] = normalized["activity_action"]
    if normalized["activity_date"]:
        where.append("CAST(created_at AS DATE) = CAST(:activity_date AS DATE)")
        params["activity_date"] = normalized["activity_date"]
    if normalized["activity_type"]:
        where.append("LOWER(COALESCE(entity_type, '')) = LOWER(:activity_type)")
        params["activity_type"] = normalized["activity_type"]
    if normalized["activity_q"]:
        where.append(
            "("
            "LOWER(COALESCE(username, '')) LIKE LOWER(:activity_q) OR "
            "LOWER(COALESCE(action, '')) LIKE LOWER(:activity_q) OR "
            "LOWER(COALESCE(entity_type, '')) LIKE LOWER(:activity_q) OR "
            "LOWER(COALESCE(details, '')) LIKE LOWER(:activity_q)"
            ")"
        )
        params["activity_q"] = f"%{normalized['activity_q']}%"

    query = "SELECT * FROM activity_logs"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT :limit"
    params["limit"] = max(1, int(limit))

    res = await db.execute(text(query), params)
    rows = res.all()
    return [_decorate_activity(dict(row._mapping)) for row in rows]


def activity_filter_values(filters: Mapping[str, str] | None = None) -> dict[str, str]:
    return _filters(filters)


async def list_activity_actions(db: AsyncSession | None = None) -> list[str]:
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _list_activity_actions_impl(session)
        return await _list_activity_actions_impl(db)

    return await async_cached_result("activity_actions_list", load, ttl_seconds=60.0)


async def _list_activity_actions_impl(db: AsyncSession) -> list[str]:
    res = await db.execute(text("SELECT DISTINCT action FROM activity_logs ORDER BY action"))
    return [str(row.action) for row in res.all() if row.action]


async def list_activity_entity_types(db: AsyncSession | None = None) -> list[str]:
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _list_activity_entity_types_impl(session)
        return await _list_activity_entity_types_impl(db)

    return await async_cached_result("activity_entity_types_list", load, ttl_seconds=60.0)


async def _list_activity_entity_types_impl(db: AsyncSession) -> list[str]:
    res = await db.execute(
        text(
            "SELECT DISTINCT entity_type FROM activity_logs WHERE COALESCE(entity_type, '') <> '' ORDER BY entity_type"
        )
    )
    return [str(row.entity_type) for row in res.all() if row.entity_type]
