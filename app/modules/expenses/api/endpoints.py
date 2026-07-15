from __future__ import annotations

from datetime import date as d_cls
from typing import List, Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_db import get_async_session
from app.api.deps import require_api_user, api_success, api_error
from app.api.v1._common import json_response

from app.modules.expenses.application.services import ExpensesService
from app.modules.expenses.api.schemas import (
    ExpenseCreateSchema,
    ExpenseUpdateSchema,
    ExpenseOutSchema,
    ExpensesListResponse,
    ExpenseDetailResponse,
    ErrorResponseSchema,
)

router = APIRouter(prefix="/api/v1", tags=["expenses"])


@router.get(
    "/expenses",
    response_model=ExpensesListResponse,
    responses={401: {"model": ErrorResponseSchema}, 403: {"model": ErrorResponseSchema}},
    summary="Lister les dépenses",
    description="Récupère la liste de toutes les dépenses enregistrées avec filtres optionnels."
)
async def api_get_expenses(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, "expenses.read")
    filters = {
        "q": request.query_params.get("q", ""),
        "category": request.query_params.get("category", ""),
        "date_from": request.query_params.get("date_from", ""),
        "date_to": request.query_params.get("date_to", ""),
    }
    service = ExpensesService(db)
    expenses = await service.list_expenses(filters)
    payloads = []
    for e in expenses:
        payloads.append(ExpenseOutSchema(
            id=e.id,
            date=e.date,
            category=e.category,
            description=e.description,
            amount=e.amount,
            payment_method=e.payment_method
        ))
    return json_response(api_success(payloads))


@router.post(
    "/expenses",
    response_model=ExpenseDetailResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponseSchema},
        401: {"model": ErrorResponseSchema},
        403: {"model": ErrorResponseSchema}
    },
    summary="Créer une nouvelle dépense",
    description="Crée une nouvelle dépense et l'enregistre en base de données."
)
async def api_create_expense(
    request: Request,
    payload: ExpenseCreateSchema,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, "expenses.write")
    service = ExpensesService(db)
    expense_id = await service.add_expense(payload)
    expense = await service.get_expense(expense_id)
    if not expense:
        api_error("internal_error", "Erreur lors de la récupération de la dépense créée", 500)
    out = ExpenseOutSchema(
        id=expense.id,
        date=expense.date,
        category=expense.category,
        description=expense.description,
        amount=expense.amount,
        payment_method=expense.payment_method
    )
    return json_response(api_success(out, status_code=201))


@router.get(
    "/expenses/{expense_id}",
    response_model=ExpenseDetailResponse,
    responses={
        401: {"model": ErrorResponseSchema},
        403: {"model": ErrorResponseSchema},
        404: {"model": ErrorResponseSchema}
    },
    summary="Récupérer le détail d'une dépense",
    description="Récupère les détails d'une dépense par son identifiant unique."
)
async def api_get_expense_detail(
    request: Request,
    expense_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, "expenses.read")
    service = ExpensesService(db)
    expense = await service.get_expense(expense_id)
    if not expense:
        api_error("not_found", "Dépense introuvable.", 404)
    out = ExpenseOutSchema(
        id=expense.id,
        date=expense.date,
        category=expense.category,
        description=expense.description,
        amount=expense.amount,
        payment_method=expense.payment_method
    )
    return json_response(api_success(out))


@router.put(
    "/expenses/{expense_id}",
    response_model=ExpenseDetailResponse,
    responses={
        400: {"model": ErrorResponseSchema},
        401: {"model": ErrorResponseSchema},
        403: {"model": ErrorResponseSchema},
        404: {"model": ErrorResponseSchema}
    },
    summary="Modifier une dépense",
    description="Modifie une dépense existante à l'aide des informations fournies."
)
async def api_update_expense(
    request: Request,
    expense_id: int,
    payload: ExpenseUpdateSchema,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, "expenses.write")
    service = ExpensesService(db)
    expense = await service.get_expense(expense_id)
    if not expense:
        api_error("not_found", "Dépense introuvable.", 404)
    await service.modify_expense(expense_id, payload)
    updated = await service.get_expense(expense_id)
    out = ExpenseOutSchema(
        id=updated.id,
        date=updated.date,
        category=updated.category,
        description=updated.description,
        amount=updated.amount,
        payment_method=updated.payment_method
    )
    return json_response(api_success(out))


@router.delete(
    "/expenses/{expense_id}",
    responses={
        401: {"model": ErrorResponseSchema},
        403: {"model": ErrorResponseSchema},
        404: {"model": ErrorResponseSchema}
    },
    summary="Supprimer une dépense",
    description="Supprime définitivement une dépense par son identifiant unique."
)
async def api_delete_expense(
    request: Request,
    expense_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, "expenses.delete")
    service = ExpensesService(db)
    success = await service.remove_expense(expense_id)
    if not success:
        api_error("not_found", "Dépense introuvable.", 404)
    return json_response(api_success({"deleted": True}))
