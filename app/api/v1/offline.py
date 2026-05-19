"""Endpoint de synchronisation des opérations saisies hors-ligne."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.deps import bearer_token, require_api_user
from app.api.v1._common import payload_to_form_data
from app.core.db_access import execute_db, query_db
from app.core.exceptions import BusinessError, ConflictError, NotFoundError, ValidationError
from app.core.permissions import (
    PERMISSION_CATALOG_READ,
    PERMISSION_CONTACTS_READ,
    PERMISSION_OPERATIONS_WRITE,
    has_permission,
)
from app.repositories.client_repository import list_clients
from app.repositories.sale_repository import build_sellable_items
from app.services.sale_service import create_sale_from_form
from app.services.payment_service import create_payment_from_form

router = APIRouter(prefix="/api/v1/offline", tags=["offline"])
logger = logging.getLogger("fabouanes")


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str | None) -> dict:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _csrf_supplied(request: Request) -> str:
    return (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-Csrf-Token")
        or ""
    )


def _require_sync_user(request: Request):
    if bearer_token(request):
        return require_api_user(request, PERMISSION_OPERATIONS_WRITE)

    expected = str(request.session.get("csrf_token") or "")
    if not expected or _csrf_supplied(request) != expected:
        raise HTTPException(
            status_code=403,
            detail={"code": "csrf_invalid", "message": "CSRF token invalide."},
        )

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Authentification requise."},
        )
    if not has_permission(user, PERMISSION_OPERATIONS_WRITE):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Permission refusée."},
        )
    return user


def _require_reference_user(request: Request):
    if bearer_token(request):
        user = require_api_user(request, PERMISSION_CONTACTS_READ)
        if not has_permission(user, PERMISSION_CATALOG_READ):
            raise HTTPException(
                status_code=403,
                detail={"code": "forbidden", "message": "Permission refusée."},
            )
        return user

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Authentification requise."},
        )
    if not has_permission(user, PERMISSION_CONTACTS_READ) or not has_permission(user, PERMISSION_CATALOG_READ):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Permission refusée."},
        )
    return user


def _receipt_for(user_id: int, client_operation_id: str):
    return query_db(
        """
        SELECT *
        FROM offline_operation_receipts
        WHERE user_id = %s AND client_operation_id = %s
        """,
        (int(user_id), client_operation_id),
        one=True,
    )


def _claim_receipt(user, client_operation_id: str, op_type: str, request_body: dict) -> tuple[int | None, dict | None]:
    if not client_operation_id:
        return None, None

    user_id = int(user["id"])
    existing = _receipt_for(user_id, client_operation_id)
    if existing:
        status = str(existing["status"] or "")
        if status == "success":
            cached = _json_loads(existing["response_json"])
            cached["duplicate"] = True
            return None, cached
        if status == "processing":
            stale = query_db(
                """
                SELECT id
                FROM offline_operation_receipts
                WHERE id = %s AND updated_at < NOW() - INTERVAL '15 minutes'
                """,
                (int(existing["id"]),),
                one=True,
            )
            if not stale:
                return None, {
                    "ok": False,
                    "error": {"code": "operation_in_progress", "message": "Synchronisation déjà en cours."},
                }
        execute_db("DELETE FROM offline_operation_receipts WHERE id = %s", (int(existing["id"]),))

    receipt_id = execute_db(
        """
        INSERT INTO offline_operation_receipts (
            user_id, client_operation_id, operation_type, status, request_json, updated_at
        ) VALUES (%s, %s, %s, 'processing', %s, CURRENT_TIMESTAMP)
        """,
        (user_id, client_operation_id, op_type, _json_dumps(request_body)),
    )
    return int(receipt_id), None


def _mark_receipt_success(receipt_id: int | None, response_payload: dict) -> None:
    if not receipt_id:
        return
    execute_db(
        """
        UPDATE offline_operation_receipts
        SET status = 'success',
            response_json = %s,
            error_message = '',
            processed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (_json_dumps(response_payload), int(receipt_id)),
    )


def _mark_receipt_failed(receipt_id: int | None, message: str) -> None:
    if not receipt_id:
        return
    execute_db(
        """
        UPDATE offline_operation_receipts
        SET status = 'failed',
            error_message = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (str(message)[:1000], int(receipt_id)),
    )


def _business_error_response(exc: BusinessError) -> JSONResponse:
    status_code = 422
    if isinstance(exc, NotFoundError):
        status_code = 404
    elif isinstance(exc, ConflictError):
        status_code = 409
    elif isinstance(exc, ValidationError):
        status_code = 422
    return JSONResponse(
        {
            "ok": False,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
        },
        status_code=status_code,
    )


@router.get("/reference-data")
async def offline_reference_data(request: Request):
    """Reference data used by the browser offline queue, authenticated by session or Bearer token."""
    _require_reference_user(request)
    clients, total = await list_clients.async_(page=1, page_size=500)
    catalog = await asyncio.to_thread(build_sellable_items)
    return JSONResponse(
        jsonable_encoder({
            "ok": True,
            "clients": clients,
            "catalog": [dict(item) for item in catalog],
            "meta": {"clients_returned": len(clients), "clients_total": total},
        })
    )


@router.post("/sync")
async def sync_operation(request: Request):
    """
    Reçoit une opération hors-ligne et l'exécute comme si elle venait du formulaire.
    Retourne 200 si succès, 4xx si erreur métier, 5xx si erreur serveur.
    """
    user = _require_sync_user(request)
    body = await request.json()

    op_type = body.get("type")
    payload = body.get("payload", {})
    client_operation_id = str(body.get("client_operation_id") or payload.get("client_operation_id") or "").strip()
    receipt_id, cached_response = _claim_receipt(user, client_operation_id, str(op_type or ""), body)
    if cached_response is not None:
        return JSONResponse(cached_response, status_code=409 if not cached_response.get("ok", True) else 200)

    try:
        if op_type == "create_sale":
            result = await asyncio.to_thread(create_sale_from_form, payload_to_form_data(payload))
            response_payload = {"ok": True, "mode": result.get("mode")}
            _mark_receipt_success(receipt_id, response_payload)
            return JSONResponse(response_payload)

        elif op_type == "create_payment":
            payment_id, payment_type = await asyncio.to_thread(
                create_payment_from_form, payload
            )
            response_payload = {"ok": True, "id": payment_id, "payment_type": payment_type}
            _mark_receipt_success(receipt_id, response_payload)
            return JSONResponse(response_payload)

        else:
            _mark_receipt_failed(receipt_id, f"Type inconnu : {op_type}")
            return JSONResponse({"error": f"Type inconnu : {op_type}"}, status_code=400)

    except BusinessError as exc:
        _mark_receipt_failed(receipt_id, exc.message)
        return _business_error_response(exc)
    except ValueError as exc:
        _mark_receipt_failed(receipt_id, str(exc))
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception as exc:
        _mark_receipt_failed(receipt_id, str(exc))
        logger.exception("Offline sync failed for operation %s", client_operation_id or "-")
        return JSONResponse({"error": "Erreur serveur"}, status_code=500)
