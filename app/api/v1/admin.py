from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import api_success, require_api_user
from app.api.v1._common import json_response, query_list_async, add_cache_headers
from app.core.permissions import PERMISSION_AUDIT_READ


router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.get("/audit-logs")
async def api_audit_logs(request: Request):
    require_api_user(request, PERMISSION_AUDIT_READ)
    rows, meta = await query_list_async(request, "SELECT * FROM audit_logs ORDER BY id DESC")
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response


@router.post("/admin/users/{user_id}/unlock")
async def api_unlock_user(user_id: int, request: Request):
    require_api_user(request, "users.write")
    from app.modules.users.repository import unlock_user_account, get_user_by_id
    from app.core.audit import audit_event
    from fastapi import HTTPException

    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    unlocked = await unlock_user_account(user_id)
    audit_event("account_unlock", "user", user_id, after={"username": user["username"]})
    return api_success({"unlocked": unlocked, "user_id": user_id})
