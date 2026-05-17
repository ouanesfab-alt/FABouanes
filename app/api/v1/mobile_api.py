from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/api/v1", tags=["mobile"])


@router.get("/ping")
async def api_ping():
    return JSONResponse({"data": {"ok": True, "service": "FABOuanes", "version": "fastapi-migration"}, "meta": {}})
