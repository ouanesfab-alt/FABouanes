from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import (
    ACCESS_TOKEN_TTL_SECONDS,
    api_success,
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



router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _response(payload: dict):
    status_code = int(payload.pop("_status_code", 200))
    return JSONResponse(payload, status_code=status_code)


@router.post("/login")
@limiter.limit("10/minute")
async def api_auth_login(request: Request):
    payload = await request.json()
    result = attempt_login(payload.get("username", ""), payload.get("password", ""))
    if not result["ok"]:
        return JSONResponse({"error": {"code": "login_failed", "message": result["message"], "details": None}}, status_code=int(result.get("status") or 401))
    user = result["user"]
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(request, user)
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
    user = validate_refresh_token(raw_refresh)
    if not user:
        return JSONResponse({"error": {"code": "refresh_token_invalid", "message": "Jeton de renouvellement invalide.", "details": None}}, status_code=401)
    access_token = create_access_token(user)
    audit_event("api_refresh", "user", user["id"], source="api", after={"username": user["username"]})
    return _response(api_success({"access_token": access_token, "token_type": "Bearer", "expires_in": ACCESS_TOKEN_TTL_SECONDS}))


@router.post("/logout")
async def api_auth_logout(request: Request):
    user = require_api_user(request)
    payload = await request.json()
    raw_refresh = str(payload.get("refresh_token", "") or "").strip()
    if raw_refresh:
        revoke_refresh_token(raw_refresh)
    else:
        revoke_all_user_tokens(int(user["id"]))
    log_activity("api_logout", "user", user["id"], f"API logout {user['username']}")
    audit_event("api_logout", "user", user["id"], source="api", after={"username": user["username"]})
    return _response(api_success({"revoked": True}))


@router.get("/me")
async def api_auth_me(request: Request):
    user = require_api_user(request)
    return _response(
        api_success(
            {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "must_change_password": bool(int(user.get("must_change_password", 0) or 0)),
                "last_login_at": user.get("last_login_at"),
                "last_password_change_at": user.get("last_password_change_at"),
            }
        )
    )
