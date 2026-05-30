"""Endpoints de synchronisation des opérations saisies hors-ligne."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_api_user, api_error
from app.api.v1._common import payload_to_form_data
from app.core.permissions import PERMISSION_OPERATIONS_WRITE
from app.services.sale_service import create_sale_from_form
from app.services.payment_service import create_payment_from_form
from app.services.purchase_service import create_purchase_from_form
from app.core.db_access import db_transaction
from app.core.idempotency import check_idempotency, save_idempotency
from app.core.exceptions import ValidationError, ConflictError
from app.core.rate_limit import limiter

logger = logging.getLogger("fabouanes.offline")
router = APIRouter(prefix="/api/v1/offline", tags=["offline"])


@router.post("/sync")
@limiter.limit("30/minute")
async def sync_operation(request: Request):
    """
    Reçoit une opération hors-ligne et l'exécute comme si elle venait du formulaire.
    Gère l'idempotence pour éviter les doublons lors des retries réseau.
    Retourne 200 si succès, 4xx si erreur métier, 5xx si erreur serveur.
    """
    require_api_user(request, PERMISSION_OPERATIONS_WRITE)
    body = await request.json()

    idempotency_key = request.headers.get("X-Idempotency-Key") or body.get("idempotency_key") or body.get("key")
    if idempotency_key:
        cached_res = check_idempotency(idempotency_key)
        if cached_res is not None:
            return JSONResponse(cached_res["content"], status_code=cached_res["status_code"])

    op_type = body.get("type")
    payload = body.get("payload", {})

    try:
        if op_type == "create_sale":
            result = await create_sale_from_form(payload_to_form_data(payload))
            res_payload = {"ok": True, "mode": result.get("mode")}
        elif op_type == "create_purchase":
            result = await create_purchase_from_form(payload_to_form_data(payload))
            res_payload = {"ok": True, "mode": result.get("mode")}
        elif op_type == "create_payment":
            payment_id, payment_type = await create_payment_from_form(payload)
            res_payload = {"ok": True, "id": payment_id, "payment_type": payment_type}
        else:
            err_res = {"success": False, "error": {"code": "unknown_type", "message": f"Type inconnu : {op_type}", "details": None}}
            if idempotency_key:
                save_idempotency(idempotency_key, {"content": err_res, "status_code": 400})
            api_error("unknown_type", f"Type inconnu : {op_type}", 400)

        if idempotency_key:
            save_idempotency(idempotency_key, {"content": res_payload, "status_code": 200})
        return JSONResponse(res_payload)

    except (ValueError, ValidationError, ConflictError) as exc:
        code = getattr(exc, "code", "validation_error")
        message = getattr(exc, "message", str(exc))
        err_res = {"success": False, "error": {"code": code, "message": message, "details": None}}
        if idempotency_key:
            save_idempotency(idempotency_key, {"content": err_res, "status_code": 422})
        api_error(code, message, 422)
    except Exception as exc:
        logger.exception("Offline sync operation failed")
        err_res = {"success": False, "error": {"code": "internal_error", "message": "Erreur serveur", "details": str(exc)}}
        if idempotency_key:
            save_idempotency(idempotency_key, {"content": err_res, "status_code": 500})
        api_error("internal_error", "Erreur serveur", 500, details=str(exc))


@router.post("/sync/bulk")
@limiter.limit("30/minute")
async def sync_operations_bulk(request: Request):
    """
    Reçoit une liste d'opérations hors-ligne et les exécute séquentiellement.
    Chaque opération est enveloppée dans sa propre transaction de base de données.
    L'idempotence est gérée individuellement par opération.
    """
    require_api_user(request, PERMISSION_OPERATIONS_WRITE)
    body = await request.json()
    operations = body.get("operations") or []

    results = []

    for op in operations:
        op_type = op.get("type")
        payload = op.get("payload", {})
        idempotency_key = op.get("idempotency_key") or op.get("key")

        # 1. Check idempotency
        if idempotency_key:
            cached_res = check_idempotency(idempotency_key)
            if cached_res is not None:
                results.append({
                    "idempotency_key": idempotency_key,
                    "status_code": cached_res["status_code"],
                    "response": cached_res["content"]
                })
                continue

        # 2. Process operation within its own transaction block
        try:
            with db_transaction():
                if op_type == "create_sale":
                    result = await create_sale_from_form(payload_to_form_data(payload))
                    res_payload = {"ok": True, "mode": result.get("mode")}
                elif op_type == "create_purchase":
                    result = await create_purchase_from_form(payload_to_form_data(payload))
                    res_payload = {"ok": True, "mode": result.get("mode")}
                elif op_type == "create_payment":
                    payment_id, payment_type = await create_payment_from_form(payload)
                    res_payload = {"ok": True, "id": payment_id, "payment_type": payment_type}
                else:
                    res_payload = {"error": f"Type inconnu : {op_type}"}
                    if idempotency_key:
                        save_idempotency(idempotency_key, {"content": res_payload, "status_code": 400})
                    results.append({
                        "idempotency_key": idempotency_key,
                        "status_code": 400,
                        "response": res_payload
                    })
                    continue

            # Save idempotency on success
            if idempotency_key:
                save_idempotency(idempotency_key, {"content": res_payload, "status_code": 200})

            results.append({
                "idempotency_key": idempotency_key,
                "status_code": 200,
                "response": res_payload
            })

        except (ValueError, ValidationError, ConflictError) as exc:
            res_payload = {"error": str(exc)}
            if idempotency_key:
                save_idempotency(idempotency_key, {"content": res_payload, "status_code": 422})
            results.append({
                "idempotency_key": idempotency_key,
                "status_code": 422,
                "response": res_payload
            })
        except Exception as exc:
            logger.exception("Bulk sync operation failed due to internal error")
            res_payload = {"error": "Erreur serveur", "details": str(exc)}
            results.append({
                "idempotency_key": idempotency_key,
                "status_code": 500,
                "response": res_payload
            })

    return JSONResponse({"results": results})
