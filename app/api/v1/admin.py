from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import api_success, require_api_user
from app.api.v1._common import add_cache_headers, json_response
from app.core.audit import audit_event, list_audit_logs
from app.core.permissions import PERMISSION_AUDIT_READ, PERMISSION_USERS_MANAGE
from app.modules.users.repository import get_user_by_id, unlock_user_account

router = APIRouter(prefix="/api/v1", tags=["admin"])


class AuditLogsResponse(BaseModel):
    success: bool = True
    data: list[dict[str, Any]]
    meta: dict[str, Any] | None = None


class UnlockUserResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]


@router.get(
    "/audit-logs",
    response_model=AuditLogsResponse,
    summary="Lister les journaux d'audit",
    description="Récupère les événements d'audit système avec pagination et filtres.",
)
async def api_audit_logs(request: Request):
    require_api_user(request, PERMISSION_AUDIT_READ)
    page = max(int(request.query_params.get("page", "1") or "1"), 1)
    page_size = min(max(int(request.query_params.get("page_size", "50") or "50"), 1), 100)
    rows = await list_audit_logs(dict(request.query_params), limit=page_size)
    meta = {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": len(rows),
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response


@router.post(
    "/admin/users/{user_id}/unlock",
    response_model=UnlockUserResponse,
    summary="Déverrouiller un compte utilisateur",
    description="Réinitialise les tentatives échouées et réactive un compte verrouillé.",
)
async def api_unlock_user(user_id: int, request: Request):
    require_api_user(request, PERMISSION_USERS_MANAGE)
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    unlocked = await unlock_user_account(user_id)
    audit_event("account_unlock", "user", user_id, after={"username": user["username"]})
    return api_success({"unlocked": unlocked, "user_id": user_id})
