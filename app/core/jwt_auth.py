"""
Authentification JWT pour l'API mobile.
Séparée des cookies de session web pour ne pas interférer.
"""
# Choix importants :
# 1. Utilisation de PyJWT pour la génération et validation sécurisée de jetons JWT autonomes.
# 2. Utilisation de la dépendance HTTPBearer de FastAPI pour une extraction transparente du token depuis l'en-tête Authorization.

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from jwt.exceptions import PyJWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return pyjwt.encode(
        {"sub": str(user_id), "role": role,
         "exp": expires, "type": "access"},
        settings.secret_key, ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    token = pyjwt.encode(
        {"sub": str(user_id), "exp": expires, "type": "refresh"},
        settings.secret_key, ALGORITHM,
    )

    # Save token hash in api_refresh_tokens
    import hashlib
    from app.core.db_helpers import execute_db
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")
    try:
        execute_db(
            """
            INSERT INTO api_refresh_tokens (user_id, token_hash, token_hint, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, token_hash, token[-8:], expires_str)
        )
    except Exception as exc:
        import logging
        logging.getLogger("fabouanes.auth").warning("Could not persist mobile refresh token in DB: %s", exc)

    return token


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = pyjwt.decode(token, settings.secret_key,
                              algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        raise HTTPException(401, "Token invalide ou expiré")


def validate_mobile_refresh_token(token: str) -> dict[str, Any]:
    # 1. Decode to verify expiration and signature
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Jeton de rafraîchissement requis")

    # 2. Check in database
    import hashlib
    from app.core.db_helpers import query_db, execute_db
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # Reuse detection check: check if it exists in db, even if revoked
    all_row = query_db("SELECT id, user_id, revoked_at FROM api_refresh_tokens WHERE token_hash = %s", (token_hash,), one=True)

    # If not found in DB, it is not a valid token (was never created or was deleted)
    if not all_row:
        raise HTTPException(401, "Jeton inconnu ou invalide")

    if all_row.get("revoked_at") is not None:
        # Replay attack detected! Revoke all tokens for this user immediately!
        user_id = int(all_row["user_id"])
        execute_db(
            "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,)
        )
        raise HTTPException(401, "Tentative de rejeu de jeton détectée, toutes les sessions ont été invalidées")

    # Mark old token as revoked/used (since we will return a rotated one!)
    execute_db(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP, last_used_at = CURRENT_TIMESTAMP WHERE id = %s",
        (int(all_row["id"]),)
    )
    return payload


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> int:
    """Dépendance FastAPI pour protéger les routes API mobile."""
    if not credentials:
        raise HTTPException(401, "Token Bearer requis")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(401, "Token d'accès requis")
    return int(payload["sub"])
