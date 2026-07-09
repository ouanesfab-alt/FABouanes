"""
API mobile — endpoints pour l'application vendeur terrain.
Auth : Bearer JWT (create_access_token / create_refresh_token).
Toutes les routes sont protégées sauf /ping et /auth/token.
"""
# Choix importants :
# 1. Utilisation de Depends(get_current_user_id) pour sécuriser tous les endpoints métier via un jeton Bearer JWT.
# 2. Exécution systématique de toutes les fonctions de repositories et services synchrones via asyncio.to_thread pour ne pas bloquer la boucle d'événements.

from __future__ import annotations
import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from app.api.v1._common import add_cache_headers
from app.core.jwt_auth import (
    create_access_token, create_refresh_token,
    decode_token, get_current_user_id,
)
from app.services.auth_service import verify_credentials
from app.modules.users.repository import get_user_by_id
from app.modules.clients.service import ClientService
from app.api.v1.clients import _fetch_client_history
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_session
from app.modules.payments.service import PaymentsService
from app.modules.reports.repository import get_dashboard_snapshot
from app.core.schema.payment_validation import PaymentCreate
from app.core.rate_limit import limiter

logger = logging.getLogger("fabouanes.mobile_api")

router = APIRouter(prefix="/api/mobile/v1", tags=["mobile"])


@router.get("/ping")
async def api_ping():
    return JSONResponse({"ok": True, "service": "FABOuanes"})


@router.post("/auth/token")
@limiter.limit("5/minute")
async def mobile_login(request: Request):
    """
    POST {"username": "...", "password": "..."} or Form/URL-encoded fields
    → {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
    """
    username = ""
    password = ""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username", "")
                password = body.get("password", "")
        except Exception as e:
            logger.warning("Failed to parse JSON body for mobile login: %s", e)
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            username = form.get("username", "")
            password = form.get("password", "")
        except Exception as e:
            logger.warning("Failed to parse Form data for mobile login: %s", e)
    else:
        # Fallback: try parsing JSON first, then Form
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username", "")
                password = body.get("password", "")
        except Exception as e1:
            logger.debug("Fallback JSON parse failed for mobile login: %s", e1)
            try:
                form = await request.form()
                username = form.get("username", "")
                password = form.get("password", "")
            except Exception as e2:
                logger.debug("Fallback Form parse failed for mobile login: %s", e2)

    user = await verify_credentials(
        str(username or "").strip(),
        str(password or ""),
    )
    if not user:
        raise HTTPException(401, "Identifiants invalides")
    return {
        "access_token": create_access_token(user["id"], user["role"]),
        "refresh_token": create_refresh_token(user["id"]),
        "token_type": "bearer",
        "user": {"id": user["id"], "username": user["username"],
                 "role": user["role"]},
    }


@router.post("/auth/refresh")
@limiter.limit("10/minute")
async def mobile_refresh(request: Request):
    """Renouvelle l'access_token depuis un refresh_token valide (JSON or Form)."""
    refresh_token = ""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                refresh_token = body.get("refresh_token", "")
        except Exception as e:
            logger.warning("Failed to parse JSON body for mobile refresh: %s", e)
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            refresh_token = form.get("refresh_token", "")
        except Exception as e:
            logger.warning("Failed to parse Form data for mobile refresh: %s", e)
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                refresh_token = body.get("refresh_token", "")
        except Exception as e1:
            logger.debug("Fallback JSON parse failed for mobile refresh: %s", e1)
            try:
                form = await request.form()
                refresh_token = form.get("refresh_token", "")
            except Exception as e2:
                logger.debug("Fallback Form parse failed for mobile refresh: %s", e2)

    if not refresh_token:
        raise HTTPException(401, "Refresh token requis")
    payload = decode_token(str(refresh_token))
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token requis")
    user = await get_user_by_id.async_(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return {
        "access_token": create_access_token(user["id"], user["role"]),
        "token_type": "bearer",
    }


@router.get("/clients")
async def mobile_list_clients(
    request: Request,
    response: Response,
    q: str = "",
    page: int = 1,
    page_size: int = 30,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """Liste les clients avec leur solde actuel. Paginé."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    service = ClientService(db)
    clients, total = await service.list_clients_with_stats(q, page, page_size)
    res_data = {"clients": clients, "total": total,
            "page": page, "page_size": page_size}
    add_cache_headers(request, response, res_data, max_age=300)
    return res_data


@router.get("/clients/{client_id}/history")
async def mobile_client_history(
    request: Request,
    response: Response,
    client_id: int,
    page: int = 1,
    page_size: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Historique complet d'un client (Zone 1 + Zone 2), paginé."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows, total = await _fetch_client_history(client_id, page, page_size)
    res_data = {"rows": rows, "total": total, "page": page}
    add_cache_headers(request, response, res_data, max_age=30)
    return res_data


@router.post("/payments")
async def mobile_record_payment(
    payload: PaymentCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Enregistre un versement depuis le terrain.
    Body/Payload: {"client_id": int, "amount": float, "payment_date": "YYYY-MM-DD",
                   "notes": str}
    """
    try:
        service = PaymentsService(db)
        result = await service.create_mobile_payment(
            client_id=payload.client_id,
            amount=payload.amount,
            payment_date=payload.payment_date,
            notes=payload.notes or "",
            recorded_by=user_id,
        )
        return result
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.get("/dashboard")
async def mobile_dashboard_summary(
    request: Request,
    response: Response,
    user_id: int = Depends(get_current_user_id),
):
    """Résumé du jour : ventes, encaissements, créances totales."""
    snapshot = await get_dashboard_snapshot.async_(date.today().isoformat())
    res_data = {
        "sales_today": snapshot["sales_today"],
        "cash_today": snapshot["cash_today"],
        "total_receivables": snapshot["total_receivables"],
        "profit_today": snapshot["profit_today"],
    }
    add_cache_headers(request, response, res_data, max_age=30)
    return res_data
