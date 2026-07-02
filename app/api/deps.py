from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, NoReturn

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings
from app.core.permissions import PERMISSION_API_ACCESS, has_permission
from app.core.audit import audit_event
import asyncio
from app.core.db_access import execute_db, query_db, execute_db_async, query_db_async
from app.modules.users.repository import get_user_by_id


ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL_DAYS = 30


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="fabouanes-api-access")


def create_access_token(user) -> str:
    return serializer().dumps({"sub": int(user["id"]), "role": user["role"], "username": user["username"]})


def refresh_token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


async def create_refresh_token(request: Request, user) -> str:
    raw_token = secrets.token_urlsafe(48)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    await execute_db_async(
        """
        INSERT INTO api_refresh_tokens (user_id, token_hash, token_hint, created_ip, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            int(user["id"]),
            refresh_token_hash(raw_token),
            raw_token[-8:],
            getattr(getattr(request, "client", None), "host", "") or "",
            request.headers.get("User-Agent", "")[:500],
            expires_at,
        ),
    )
    return raw_token


def decode_access_token(raw_token: str):
    try:
        payload = serializer().loads(raw_token, max_age=ACCESS_TOKEN_TTL_SECONDS)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail={"code": "access_token_expired", "message": "Le jeton d'acces a expire."}) from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail={"code": "access_token_invalid", "message": "Jeton d'acces invalide."}) from exc
    user = get_user_by_id(int(payload.get("sub", 0) or 0))
    if not user or not int(user.get("is_active", 1) or 0):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Utilisateur indisponible."})
    return user


def bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def api_success(data: Any, meta: dict[str, Any] | None = None, status_code: int = 200):
    return {"success": True, "data": data, "meta": meta or {}, "_status_code": status_code}


def api_error(code: str, message: str, status_code: int, details: Any = None) -> NoReturn:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message, "details": details})


def require_api_user(request: Request, permission: str | None = None):
    raw_token = bearer_token(request)
    if not raw_token:
        api_error("unauthorized", "Jeton Bearer requis.", status.HTTP_401_UNAUTHORIZED)
    user = decode_access_token(raw_token)
    if not has_permission(user, PERMISSION_API_ACCESS) or (permission and not has_permission(user, permission)):
        audit_event(
            "permission_denied",
            "api",
            request.url.path,
            source="api",
            status="failure",
            actor={"id": user["id"], "username": user["username"], "role": user["role"]},
            meta={"permission": permission},
        )
        api_error("forbidden", "Permission refusee.", status.HTTP_403_FORBIDDEN, {"permission": permission})
    request.state.user = user
    return user


async def revoke_refresh_token(raw_token: str) -> None:
    await execute_db_async(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = %s AND revoked_at IS NULL",
        (refresh_token_hash(raw_token),),
    )


async def revoke_all_user_tokens(user_id: int) -> None:
    await execute_db_async(
        "UPDATE api_refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = %s AND revoked_at IS NULL",
        (int(user_id),),
    )


async def validate_refresh_token(raw_token: str):
    row = await query_db_async(
        """
        SELECT id, user_id, expires_at
        FROM api_refresh_tokens
        WHERE token_hash = %s
          AND revoked_at IS NULL
          AND expires_at >= CURRENT_TIMESTAMP
        """,
        (refresh_token_hash(raw_token),),
        one=True,
    )
    if not row:
        return None
    user = await asyncio.to_thread(get_user_by_id, int(row["user_id"]))
    if not user or not int(user.get("is_active", 1) or 0):
        await revoke_refresh_token(raw_token)
        return None
    await execute_db_async("UPDATE api_refresh_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = %s", (int(row["id"]),))
    return user
