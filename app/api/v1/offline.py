"""Endpoint de synchronisation des opérations saisies hors-ligne."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_api_user
from app.api.v1._common import payload_to_form_data
from app.core.permissions import PERMISSION_OPERATIONS_WRITE
from app.services.sale_service import create_sale_from_form
from app.services.payment_service import create_payment_from_form
from app.services.purchase_service import create_purchase_from_form

router = APIRouter(prefix="/api/v1/offline", tags=["offline"])


@router.post("/sync")
async def sync_operation(request: Request):
    """
    Reçoit une opération hors-ligne et l'exécute comme si elle venait du formulaire.
    Retourne 200 si succès, 4xx si erreur métier, 5xx si erreur serveur.
    """
    require_api_user(request, PERMISSION_OPERATIONS_WRITE)
    body = await request.json()

    op_type = body.get("type")
    payload = body.get("payload", {})

    try:
        if op_type == "create_sale":
            result = await asyncio.to_thread(create_sale_from_form, payload_to_form_data(payload))
            return JSONResponse({"ok": True, "mode": result.get("mode")})

        elif op_type == "create_purchase":
            result = await asyncio.to_thread(create_purchase_from_form, payload_to_form_data(payload))
            return JSONResponse({"ok": True, "mode": result.get("mode")})

        elif op_type == "create_payment":
            payment_id, payment_type = await asyncio.to_thread(
                create_payment_from_form, payload
            )
            return JSONResponse({"ok": True, "id": payment_id, "payment_type": payment_type})

        else:
            return JSONResponse({"error": f"Type inconnu : {op_type}"}, status_code=400)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception:
        return JSONResponse({"error": "Erreur serveur"}, status_code=500)
