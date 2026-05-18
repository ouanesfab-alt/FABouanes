from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from app.core.db_access import query_db
from app.core.activity import log_error


ACTION_LABELS = {
    "backup_now": "a cree une sauvegarde",
    "change_password": "a change un mot de passe",
    "create_client": "a cree un client",
    "create_payment": "a enregistre un paiement",
    "create_production": "a cree une production",
    "create_purchase": "a cree un achat",
    "create_purchase_document": "a cree un bon d'achat",
    "create_sale": "a cree une vente",
    "create_sale_document": "a cree une facture",
    "create_supplier": "a cree un fournisseur",
    "create_user": "a cree un utilisateur",
    "delete_payment": "a supprime un paiement",
    "delete_production": "a supprime une production",
    "delete_purchase": "a supprime un achat",
    "delete_sale": "a supprime une vente",
    "edit_production_notes": "a modifie une production",
    "import_clients_excel": "a importe des clients Excel",
    "login": "s'est connecte",
    "logout": "s'est deconnecte",
    "restore_backup": "a restaure une sauvegarde",
    "update_backup_settings": "a modifie les sauvegardes",
    "update_client": "a modifie un client",
    "update_payment": "a modifie un paiement",
    "update_price": "a modifie un prix",
    "update_production": "a modifie une production",
    "update_purchase": "a modifie un achat",
    "update_purchase_document": "a modifie un bon d'achat",
    "update_sale": "a modifie une vente",
    "update_sale_document": "a modifie une facture",
    "update_supplier": "a modifie un fournisseur",
    "update_user": "a modifie un utilisateur",
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
    "settings": "parametres",
    "supplier": "fournisseur",
    "user": "utilisateur",
}


def _display_date(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M")
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw[:19], fmt)
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


def list_admin_activity(filters: Mapping[str, str] | None = None, *, limit: int = 80) -> list[dict]:
    normalized = _filters(filters)
    where: list[str] = []
    params: list[object] = []
    if normalized["activity_user"]:
        where.append("LOWER(username) LIKE LOWER(%s)")
        params.append(f"%{normalized['activity_user']}%")
    if normalized["activity_action"]:
        where.append("LOWER(action) = LOWER(%s)")
        params.append(normalized["activity_action"])
    if normalized["activity_date"]:
        where.append("CAST(created_at AS DATE) = CAST(%s AS DATE)")
        params.append(normalized["activity_date"])
    if normalized["activity_type"]:
        where.append("LOWER(COALESCE(entity_type, '')) = LOWER(%s)")
        params.append(normalized["activity_type"])
    if normalized["activity_q"]:
        where.append(
            "("
            "LOWER(COALESCE(username, '')) LIKE LOWER(%s) OR "
            "LOWER(COALESCE(action, '')) LIKE LOWER(%s) OR "
            "LOWER(COALESCE(entity_type, '')) LIKE LOWER(%s) OR "
            "LOWER(COALESCE(details, '')) LIKE LOWER(%s)"
            ")"
        )
        like = f"%{normalized['activity_q']}%"
        params.extend([like, like, like, like])
    query = "SELECT * FROM activity_logs"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT %s"
    rows = query_db(query, tuple(params + [max(1, int(limit))]))
    return [_decorate_activity(row) for row in rows]


def activity_filter_values(filters: Mapping[str, str] | None = None) -> dict[str, str]:
    return _filters(filters)


def list_activity_actions() -> list[str]:
    rows = query_db("SELECT DISTINCT action FROM activity_logs ORDER BY action")
    return [str(row["action"]) for row in rows if row["action"]]


def list_activity_entity_types() -> list[str]:
    rows = query_db("SELECT DISTINCT entity_type FROM activity_logs WHERE COALESCE(entity_type, '') <> '' ORDER BY entity_type")
    return [str(row["entity_type"]) for row in rows if row["entity_type"]]
