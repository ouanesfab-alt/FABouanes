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
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.core.jwt_auth import (
    create_access_token, create_refresh_token,
    decode_token, get_current_user_id,
)

router = APIRouter(prefix="/api/v1", tags=["mobile"])


@router.get("/ping")
async def api_ping():
    return JSONResponse({"ok": True, "service": "FABOuanes"})


@router.post("/auth/token")
async def mobile_login(body: dict):
    """
    POST {"username": "...", "password": "..."}
    → {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
    """
    from app.services.auth_service import verify_credentials
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
async def mobile_refresh(body: dict):
    """Renouvelle l'access_token depuis un refresh_token valide."""
    payload = decode_token(body.get("refresh_token", ""))
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token requis")
    from app.repositories.user_repository import get_user_by_id
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
    from app.repositories.client_repository import list_clients_with_balance
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
    from app.api.v1.clients import _fetch_client_history
    rows, total = await asyncio.to_thread(
        _fetch_client_history, client_id, page, page_size
    )
    return {"rows": rows, "total": total, "page": page}


@router.post("/mobile/payments")
async def mobile_record_payment(
    body: dict,
    user_id: int = Depends(get_current_user_id),
):
    """
    Enregistre un versement depuis le terrain.
    Body: {"client_id": int, "amount": float, "payment_date": "YYYY-MM-DD",
           "notes": str}
    """
    from app.services.payment_service import create_mobile_payment
    result = await asyncio.to_thread(
        create_mobile_payment,
        client_id=int(body.get("client_id", 0)),
        amount=float(body.get("amount", 0)),
        payment_date=str(body.get("payment_date", "")),
        notes=str(body.get("notes", "")),
        recorded_by=user_id,
    )
    return result


@router.get("/mobile/dashboard")
async def mobile_dashboard_summary(
    user_id: int = Depends(get_current_user_id),
):
    """Résumé du jour : ventes, encaissements, créances totales."""
    from app.repositories.dashboard_repository import get_dashboard_snapshot
    from datetime import date
    snapshot = await asyncio.to_thread(
        get_dashboard_snapshot, date.today().isoformat()
    )
    return {
        "sales_today": snapshot["sales_today"],
        "cash_today": snapshot["cash_today"],
        "total_receivables": snapshot["total_receivables"],
        "profit_today": snapshot["profit_today"],
    }
