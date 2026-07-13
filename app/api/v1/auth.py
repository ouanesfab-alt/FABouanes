from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import (
    ACCESS_TOKEN_TTL_SECONDS,
    api_success,
    api_error,
    create_access_token,
    create_refresh_token,
    require_api_user,
    revoke_all_user_tokens,
    revoke_refresh_token,
    validate_refresh_token,
)
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.services.auth_service import attempt_login
from app.core.rate_limit import limiter
from app.core.schema.auth_validation import LoginRequest as UserLoginSchema


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _response(payload: dict):
    status_code = int(payload.pop("_status_code", 200))
    return JSONResponse(payload, status_code=status_code)


@router.post("/login")
@limiter.limit("10/minute")
async def api_auth_login(request: Request, payload: UserLoginSchema):
    result = await attempt_login(payload.username, payload.password)
    if not result["ok"]:
        api_error("login_failed", result["message"], int(result.get("status") or 401))
    user = result["user"]
    access_token = create_access_token(user)
    refresh_token = await create_refresh_token(request, user)
    audit_event("api_login", "user", user["id"], source="api", after={"username": user["username"]})
    return _response(
        api_success(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                    "must_change_password": bool(int(user.get("must_change_password", 0) or 0)),
                },
            }
        )
    )


@router.post("/refresh")
async def api_auth_refresh(request: Request):
    payload = await request.json()
    raw_refresh = str(payload.get("refresh_token", "") or "").strip()
    user = await validate_refresh_token(raw_refresh)
    if not user:
        api_error("refresh_token_invalid", "Jeton de renouvellement invalide.", 401)
    access_token = create_access_token(user)
    new_refresh = await create_refresh_token(request, user)
    await asyncio.to_thread(audit_event, "api_refresh", "user", user["id"], source="api", after={"username": user["username"]})
    return _response(
        api_success({
            "access_token": access_token,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS
        })
    )



@router.post("/logout")
async def api_auth_logout(request: Request):
    user = await asyncio.to_thread(require_api_user, request)
    payload = await request.json()
    raw_refresh = str(payload.get("refresh_token", "") or "").strip()
    if raw_refresh:
        await revoke_refresh_token(raw_refresh)
    else:
        await revoke_all_user_tokens(int(user["id"]))
    await asyncio.to_thread(log_activity, "api_logout", "user", user["id"], f"API logout {user['username']}")
    await asyncio.to_thread(audit_event, "api_logout", "user", user["id"], source="api", after={"username": user["username"]})
    return _response(api_success({"revoked": True}))


@router.get("/me")
async def api_auth_me(request: Request):
    user = await asyncio.to_thread(require_api_user, request)
    return _response(
        api_success(
            {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "must_change_password": bool(int(user.get("must_change_password", 0) or 0)),
                "last_login_at": user.get("last_login_at").isoformat() if hasattr(user.get("last_login_at"), "isoformat") else str(user.get("last_login_at")) if user.get("last_login_at") else None,
                "last_password_change_at": user.get("last_password_change_at").isoformat() if hasattr(user.get("last_password_change_at"), "isoformat") else str(user.get("last_password_change_at")) if user.get("last_password_change_at") else None,
            }
        )
    )
