from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import asyncio

from app.api.deps import require_api_user
from app.core.permissions import PERMISSION_DASHBOARD_READ
from app.repositories.dashboard_repository import get_dashboard_snapshot


router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary")
async def api_dashboard_summary(request: Request):
    require_api_user(request, PERMISSION_DASHBOARD_READ)
    snapshot = await asyncio.to_thread(get_dashboard_snapshot, request.query_params.get("date"))
    return JSONResponse(jsonable_encoder({"data": dict(snapshot), "meta": {}}))

