"""
API mobile — endpoints pour l'application vendeur terrain.
Auth : Bearer JWT (create_access_token / create_refresh_token).
Toutes les routes sont protégées sauf /ping et /auth/token.
"""
# Choix importants :
# 1. Utilisation de Depends(get_current_user_id) pour sécuriser tous les endpoints métier via un jeton Bearer JWT.
# 2. Exécution systématique de toutes les fonctions de repositories et services synchrones via asyncio.to_thread pour ne pas bloquer la boucle d'événements.

from __future__ import annotations
import asyncio
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.jwt_auth import (
    create_access_token, create_refresh_token,
    decode_token, get_current_user_id,
)
from app.services.auth_service import verify_credentials
from app.repositories.user_repository import get_user_by_id
from app.repositories.client_repository import list_clients_with_balance
from app.api.v1.clients import _fetch_client_history
from app.services.payment_service import create_mobile_payment
from app.repositories.dashboard_repository import get_dashboard_snapshot
from app.schemas.payment import PaymentCreate
from app.core.rate_limit import limiter

router = APIRouter(prefix="/api/v1", tags=["mobile"])


@router.get("/ping")
async def api_ping():
    return JSONResponse({"ok": True, "service": "FABOuanes"})


@router.post("/auth/token")
@limiter.limit("5/minute")
async def mobile_login(request: Request, body: dict):
    """
    POST {"username": "...", "password": "..."}
    → {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
    """
    # verify_credentials doit retourner None si échec, user dict si succès
    user = await asyncio.to_thread(
        verify_credentials,
        body.get("username", ""),
        body.get("password", ""),
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
async def mobile_refresh(request: Request, body: dict):
    """Renouvelle l'access_token depuis un refresh_token valide."""
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Refresh token requis")
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token requis")
    user = await asyncio.to_thread(get_user_by_id, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return {
        "access_token": create_access_token(user["id"], user["role"]),
        "token_type": "bearer",
    }


@router.get("/mobile/clients")
async def mobile_list_clients(
    q: str = "",
    page: int = 1,
    page_size: int = 30,
    user_id: int = Depends(get_current_user_id),
):
    """Liste les clients avec leur solde actuel. Paginé."""
    clients, total = await asyncio.to_thread(
        list_clients_with_balance, q, page, page_size
    )
    return {"clients": clients, "total": total,
            "page": page, "page_size": page_size}


@router.get("/mobile/clients/{client_id}/history")
async def mobile_client_history(
    client_id: int,
    page: int = 1,
    page_size: int = 50,
    user_id: int = Depends(get_current_user_id),
):
    """Historique complet d'un client (Zone 1 + Zone 2), paginé."""
    rows, total = await asyncio.to_thread(
        _fetch_client_history, client_id, page, page_size
    )
    return {"rows": rows, "total": total, "page": page}


@router.post("/mobile/payments")
async def mobile_record_payment(
    payload: PaymentCreate,
    user_id: int = Depends(get_current_user_id),
):
    """
    Enregistre un versement depuis le terrain.
    Body/Payload: {"client_id": int, "amount": float, "payment_date": "YYYY-MM-DD",
                   "notes": str}
    """
    try:
        result = await asyncio.to_thread(
            create_mobile_payment,
            client_id=payload.client_id,
            amount=payload.amount,
            payment_date=payload.payment_date,
            notes=payload.notes or "",
            recorded_by=user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/mobile/dashboard")
async def mobile_dashboard_summary(
    user_id: int = Depends(get_current_user_id),
):
    """Résumé du jour : ventes, encaissements, créances totales."""
    snapshot = await asyncio.to_thread(
        get_dashboard_snapshot, date.today().isoformat()
    )
    return {
        "sales_today": snapshot["sales_today"],
        "cash_today": snapshot["cash_today"],
        "total_receivables": snapshot["total_receivables"],
        "profit_today": snapshot["profit_today"],
    }
