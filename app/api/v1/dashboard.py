from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import require_api_user, api_success
from app.core.permissions import PERMISSION_DASHBOARD_READ
from app.repositories.dashboard_repository import get_dashboard_snapshot

from app.api.v1._common import add_cache_headers, json_response

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary")
async def api_dashboard_summary(request: Request):
    require_api_user(request, PERMISSION_DASHBOARD_READ)
    snapshot = await get_dashboard_snapshot.async_(request.query_params.get("date"))
    res_data = api_success(dict(snapshot))
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

