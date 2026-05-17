from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import api_success, require_api_user
from app.api.v1._common import json_response, query_list
from app.core.permissions import PERMISSION_AUDIT_READ


router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.get("/audit-logs")
async def api_audit_logs(request: Request):
    require_api_user(request, PERMISSION_AUDIT_READ)
    rows, meta = query_list(request, "SELECT * FROM audit_logs ORDER BY id DESC")
    return json_response(api_success(rows, meta))
