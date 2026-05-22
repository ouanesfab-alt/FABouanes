from __future__ import annotations

import re
from fastapi import Request

from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import APP_DATA_DIR, DEFAULT_ADMIN_USERNAME
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.permissions import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, normalize_role
from app.repositories.user_repository import (
    get_user_by_id,
    get_user_by_username,
    touch_login,
    update_password,
)
from app.core.security import (
    client_ip,
    consume_rate_limit,
    validate_password_strength,
    is_locked_out,
    record_login_failure,
    clear_login_failures,
)

VALID_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR}


def attempt_login(username: str, password: str, request: Request | None = None):
    normalized = (username or "").strip()
    ip = client_ip()
    
    # 1. Check IP lockout first
    if is_locked_out(ip):
        audit_event(
            action="login",
            entity_type="user",
            entity_id=normalized or None,
            status="failure",
            actor={"username": normalized or "anonymous", "role": "anonymous"},
            meta={"reason": "locked_out", "ip": ip},
        )
        return {"ok": False, "status": 429, "message": "Trop d'echecs de connexion. Votre IP est temporairement bloquee."}

    # 2. Check standard rate limit (réduit à 5 tentatives / 5 minutes)
    login_key = f"login:{ip}:{normalized.lower()}"
    if not consume_rate_limit(login_key, 5, 300):
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
        clear_login_failures(ip)  # Clear failures on success
        touch_login(int(user["id"]))
        user = get_user_by_username(normalized)
        log_activity("login", "user", user["id"], f"Connexion de {normalized}")
        audit_event("login", "user", user["id"], after={"username": normalized, "role": user["role"]})
        
        # Rotation de session pour empêcher la fixation de session
        if request and hasattr(request, "session"):
            old_data = dict(request.session)
            request.session.clear()
            request.session.update(old_data)
            request.session["user_id"] = int(user["id"])
            request.session["role"] = user["role"]
            request.session["username"] = normalized

        return {"ok": True, "user": user}

        
    # Failed attempt
    record_login_failure(ip)
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
    if str(user["username"]) == DEFAULT_ADMIN_USERNAME:
        try:
            (APP_DATA_DIR / "first_admin_password.txt").unlink(missing_ok=True)
        except Exception:
            pass
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


def verify_credentials(username: str, password: str) -> dict | None:
    """
    Vérifie les identifiants d'un utilisateur et retourne ses informations s'ils sont valides.
    Utilisé par l'API mobile.
    """
    res = attempt_login(username, password)
    if res.get("ok") and "user" in res:
        return res["user"]
    return None

