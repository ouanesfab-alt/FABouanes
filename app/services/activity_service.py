from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_sessionmaker


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
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_activity_actions_impl(session)
    return await _list_activity_actions_impl(db)


async def _list_activity_actions_impl(db: AsyncSession) -> list[str]:
    res = await db.execute(text("SELECT DISTINCT action FROM activity_logs ORDER BY action"))
    return [str(row.action) for row in res.all() if row.action]


async def list_activity_entity_types(db: AsyncSession | None = None) -> list[str]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_activity_entity_types_impl(session)
    return await _list_activity_entity_types_impl(db)


async def _list_activity_entity_types_impl(db: AsyncSession) -> list[str]:
    res = await db.execute(text("SELECT DISTINCT entity_type FROM activity_logs WHERE COALESCE(entity_type, '') <> '' ORDER BY entity_type"))
    return [str(row.entity_type) for row in res.all() if row.entity_type]
