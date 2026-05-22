"""
Authentification JWT pour l'API mobile.
Séparée des cookies de session web pour ne pas interférer.
"""
# Choix importants :
# 1. Utilisation de python-jose pour la génération et validation sécurisée de jetons JWT autonomes.
# 2. Utilisation de la dépendance HTTPBearer de FastAPI pour une extraction transparente du token depuis l'en-tête Authorization.

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
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
    return jwt.encode(
        {"sub": str(user_id), "role": role,
         "exp": expires, "type": "access"},
        settings.secret_key, ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expires, "type": "refresh"},
        settings.secret_key, ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key,
                             algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(401, "Token invalide ou expiré")


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
