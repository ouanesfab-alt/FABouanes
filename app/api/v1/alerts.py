from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response
from app.core.async_db import get_async_session
from app.core.models import StockAlert
from app.core.permissions import PERMISSION_CATALOG_READ, PERMISSION_CATALOG_WRITE

router = APIRouter(prefix="/api/v1", tags=["alerts"])


@router.get("/alerts")
async def api_get_alerts(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_READ)
    stmt = select(StockAlert).where(StockAlert.acknowledged_at.is_(None)).order_by(StockAlert.triggered_at.desc())
    res = await db.execute(stmt)
    alerts = res.scalars().all()
    rows = [a.model_dump() for a in alerts]
    return json_response(api_success(rows))


@router.post("/alerts/{alert_id}/acknowledge")
async def api_acknowledge_alert(request: Request, alert_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    alert = await db.get(StockAlert, alert_id)
    if not alert:
        api_error("not_found", "Alerte introuvable.", 404)
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now()
        await db.commit()
    return json_response(api_success({"acknowledged": True}))
