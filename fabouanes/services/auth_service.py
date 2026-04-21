from __future__ import annotations

import re

from werkzeug.security import check_password_hash, generate_password_hash

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.permissions import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, normalize_role
from fabouanes.repositories.user_repository import (
    get_user_by_id,
    get_user_by_username,
    touch_login,
    update_password,
)
from fabouanes.security import client_ip, consume_rate_limit, validate_password_strength

VALID_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR}


def attempt_login(username: str, password: str):
    normalized = (username or "").strip()
    login_key = f"login:{client_ip()}:{normalized.lower()}"
    if not consume_rate_limit(login_key, 8, 300):
        audit_event(
            action="login",
            entity_type="user",
            entity_id=normalized or None,
            status="failure",
            actor={"username": normalized or "anonymous", "role": "anonymous"},
            meta={"reason": "rate_limited"},
        )
        return {"ok": False, "status": 429, "message": "Trop de tentatives de connexion. Reessaie dans 5 minutes."}
    user = get_user_by_username(normalized)
    if user and int(user.get("is_active", 1) or 0) and check_password_hash(user["password_hash"], password or ""):
        touch_login(int(user["id"]))
        user = get_user_by_username(normalized)
        log_activity("login", "user", user["id"], f"Connexion de {normalized}")
        audit_event("login", "user", user["id"], after={"username": normalized, "role": user["role"]})
        return {"ok": True, "user": user}
    reason = "inactive" if user and not int(user.get("is_active", 1) or 0) else "invalid_credentials"
    audit_event(
        action="login",
        entity_type="user",
        entity_id=user["id"] if user else normalized or None,
        status="failure",
        actor={"username": normalized or "anonymous", "role": user["role"] if user else "anonymous"},
        meta={"reason": reason},
    )
    return {"ok": False, "status": 401, "message": "Nom d'utilisateur ou mot de passe incorrect."}


def change_user_password(user_id: int, current_password: str, new_password: str, confirm_password: str):
    user = get_user_by_id(user_id)
    if not user or not check_password_hash(user["password_hash"], current_password or ""):
        audit_event(
            action="change_password",
            entity_type="user",
            entity_id=user_id,
            status="failure",
            meta={"reason": "invalid_current_password"},
        )
        return {"ok": False, "message": "Mot de passe actuel incorrect."}
    ok, password_msg = validate_password_strength(new_password or "")
    if not ok:
        return {"ok": False, "message": password_msg}
    if (new_password or "") != (confirm_password or ""):
        return {"ok": False, "message": "La confirmation du mot de passe ne correspond pas."}
    before = {"must_change_password": int(user["must_change_password"] or 0)}
    update_password(user_id, generate_password_hash(new_password), 0)
    updated_user = get_user_by_id(user_id)
    log_activity("change_password", "user", user_id, f"Changement du mot de passe pour {user['username']}")
    audit_event(
        "change_password",
        "user",
        user_id,
        before=before,
        after={"must_change_password": int(updated_user["must_change_password"] or 0), "last_password_change_at": updated_user["last_password_change_at"]},
    )
    return {"ok": True, "message": "Mot de passe mis a jour."}


def validate_new_user_payload(username: str, password: str, role: str):
    normalized = (username or "").strip()
    if not normalized or not password:
        return {"ok": False, "message": "Nom d'utilisateur et mot de passe obligatoires."}
    ok, password_msg = validate_password_strength(password)
    if not ok:
        return {"ok": False, "message": password_msg}
    role_value = normalize_role(role)
    if role_value not in VALID_ROLES:
        return {"ok": False, "message": "Role invalide."}
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", normalized):
        return {"ok": False, "message": "Nom d'utilisateur invalide. Utilise 3 a 50 caracteres: lettres, chiffres, point, tiret, underscore."}
    return {"ok": True, "username": normalized, "role": role_value}

