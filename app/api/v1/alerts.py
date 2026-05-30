from __future__ import annotations

import asyncio
from fastapi import APIRouter, Request

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response
from app.core.db_access import execute_db_async, query_db_async
from app.core.permissions import PERMISSION_CATALOG_READ, PERMISSION_CATALOG_WRITE

router = APIRouter(prefix="/api/v1", tags=["alerts"])


@router.get("/alerts")
async def api_get_alerts(request: Request):
    require_api_user(request, PERMISSION_CATALOG_READ)
    rows = await query_db_async(
        "SELECT id, product_type, product_id, product_name, current_qty, threshold_qty, triggered_at FROM stock_alerts WHERE acknowledged_at IS NULL ORDER BY triggered_at DESC"
    )
    return json_response(api_success(rows or []))


@router.post("/alerts/{alert_id}/acknowledge")
async def api_acknowledge_alert(request: Request, alert_id: int):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    
    # Check if alert exists
    exists = await query_db_async(
        "SELECT id FROM stock_alerts WHERE id = %s",
        (alert_id,),
        one=True
    )
    if not exists:
        api_error("not_found", "Alerte introuvable.", 404)
        
    # Mark as acknowledged
    await execute_db_async(
        "UPDATE stock_alerts SET acknowledged_at = NOW() WHERE id = %s AND acknowledged_at IS NULL",
        (alert_id,)
    )
    return json_response(api_success({"acknowledged": True}))
