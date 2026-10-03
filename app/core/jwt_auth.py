"""
Authentification JWT pour l'API mobile.
Séparée des cookies de session web pour ne pas interférer.
"""
# Choix importants :
# 1. Utilisation de PyJWT pour la génération et validation sécurisée de jetons JWT autonomes.
# 2. Utilisation de la dépendance HTTPBearer de FastAPI pour une extraction transparente du token depuis l'en-tête Authorization.

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError

from app.core import db_helpers
from app.core.config import settings
from app.core.permissions import has_permission


def execute_db(*args, **kwargs):
    return db_helpers.execute_db(*args, **kwargs)


def query_db(*args, **kwargs):
    return db_helpers.query_db(*args, **kwargs)

logger = logging.getLogger("fabouanes.auth")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return pyjwt.encode(
        {"sub": str(user_id), "role": role, "exp": expires, "type": "access"},
        settings.secret_key,
        ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid.uuid4().hex
    token = pyjwt.encode(
        {"sub": str(user_id), "exp": expires, "type": "refresh", "jti": jti},
        settings.secret_key,
        ALGORITHM,
    )

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")
    try:
        execute_db(
            """
            INSERT INTO api_refresh_tokens (user_id, token_hash, token_hint, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, token_hash, token[-8:], expires_str),
        )
    except Exception as exc:
        logger.error(
            "Could not persist mobile refresh token in DB: %s", exc, exc_info=True
        )
        raise HTTPException(500, "Impossible de sécuriser la session mobile")

    return token


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = pyjwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        raise HTTPException(401, "Token invalide ou expiré")


def validate_mobile_refresh_token(token: str) -> dict[str, Any]:
    # 1. Decode to verify expiration and signature
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Jeton de rafraîchissement requis")

    # 2. Check in database
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    all_row = query_db(
        "SELECT id, user_id, revoked_at FROM api_refresh_tokens WHERE token_hash = %s", (token_hash,), one=True
    )

    if not all_row:
        raise HTTPException(401, "Jeton inconnu ou invalide")

    user_id = int(all_row["user_id"])

    if all_row.get("revoked_at") is not None:
        execute_db(
            "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
        raise HTTPException(401, "Tentative de rejeu de jeton détectée, toutes les sessions ont été invalidées")

    user_row = query_db("SELECT id, is_active FROM users WHERE id = %s", (user_id,), one=True)
    if user_row is not None and not bool(user_row.get("is_active", 1)):
        raise HTTPException(401, "Compte utilisateur inactif ou désactivé")

    execute_db(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = %s",
        (int(all_row["id"]),),
    )
    return payload


def rotate_mobile_refresh_token(token: str) -> tuple[dict[str, Any], str]:
    """Atomically validate the existing refresh token, mark it revoked, and issue a new refresh token.

    Returns (user_dict, new_refresh_token).
    Executes in a single database transaction.
    """
    with db_helpers.db_manager.db_transaction():
        payload = validate_mobile_refresh_token(token)
        user_id = int(payload["sub"])
        user_row = query_db("SELECT id, username, role, is_active FROM users WHERE id = %s", (user_id,), one=True)
        user_dict = dict(user_row) if user_row else {"id": user_id, "username": "user", "role": "operator", "is_active": True}
        new_token = create_refresh_token(user_id)
        return user_dict, new_token


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> int:
    """Dépendance FastAPI pour obtenir l'ID utilisateur mobile."""
    if not credentials:
        raise HTTPException(401, "Token Bearer requis")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(401, "Token d'accès requis")

    user_id = int(payload["sub"])
    user_row = query_db("SELECT id, is_active FROM users WHERE id = %s", (user_id,), one=True)
    if not user_row or not user_row.get("is_active"):
        raise HTTPException(401, "Compte utilisateur inactif ou désactivé")
    return user_id


def require_mobile_permission(permission: str):
    """Dépendance pour vérifier une permission fine sur une route mobile."""

    def dependency(user_id: int = Security(get_current_user_id)) -> dict[str, Any]:
        user_row = query_db(
            "SELECT id, username, role, is_active, custom_permissions_json FROM users WHERE id = %s",
            (int(user_id),),
            one=True,
        )
        user = dict(user_row) if user_row else {"id": int(user_id), "role": "admin", "is_active": True}
        if not has_permission(user, permission):
            raise HTTPException(403, "Accès refusé pour cette ressource mobile")
        return user

    return dependency
