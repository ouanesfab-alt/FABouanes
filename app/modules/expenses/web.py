"""Routes web du module Dépenses & Charges."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.modules.expenses.service import (
    add_expense, get_categories, get_expense, get_payment_methods,
    list_expenses, modify_expense, remove_expense,
)
from app.modules.expenses.repository import expenses_total, expenses_by_category
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates

router = APIRouter()


def _parse_amount(raw) -> float:
    try:
        return float(str(raw or "0").replace(",", ".").replace(" ", "").strip() or "0")
    except (ValueError, TypeError):
        return 0.0


@router.get("/expenses", name="expenses")
async def expenses_page(request: Request):
    denied = require_permission(request, "expenses.read")
    if denied:
        return denied
    filters = {
        "q": request.query_params.get("q", ""),
        "category": request.query_params.get("category", ""),
        "date_from": request.query_params.get("date_from", ""),
        "date_to": request.query_params.get("date_to", ""),
    }
    expenses = list_expenses(filters)
    total = sum(e.get("amount", 0) for e in expenses)
    by_category = expenses_by_category(filters.get("date_from"), filters.get("date_to"))
    return templates.TemplateResponse("expenses.html", template_context(
        request, expenses=expenses, categories=get_categories(),
        payment_methods=get_payment_methods(), filters=filters,
        total=total, by_category=by_category, title="Dépenses & Charges",
    ))


@router.get("/expenses/new", name="new_expense")
async def new_expense_page(request: Request):
    denied = require_permission(request, "expenses.write")
    if denied:
        return denied
    return templates.TemplateResponse("expense_form.html", template_context(
        request, expense=None, categories=get_categories(),
        payment_methods=get_payment_methods(), title="Nouvelle dépense",
    ))


@router.post("/expenses/new", name="new_expense")
async def new_expense_submit(request: Request):
    denied = require_permission(request, "expenses.write")
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    add_expense(
        date=str(form.get("date", "")).strip(),
        category=str(form.get("category", "general")).strip(),
        description=str(form.get("description", "")).strip(),
        amount=_parse_amount(form.get("amount")),
        method=str(form.get("payment_method", "cash")).strip(),
    )
    flash(request, "Dépense ajoutée avec succès.", "success")
    return RedirectResponse("/expenses", status_code=303)


@router.get("/expenses/{expense_id}/edit", name="edit_expense")
async def edit_expense_page(request: Request, expense_id: int):
    denied = require_permission(request, "expenses.write")
    if denied:
        return denied
    expense = get_expense(expense_id)
    if not expense:
        flash(request, "Dépense introuvable.", "danger")
        return RedirectResponse("/expenses", status_code=303)
    return templates.TemplateResponse("expense_form.html", template_context(
        request, expense=expense, categories=get_categories(),
        payment_methods=get_payment_methods(), title="Modifier la dépense",
    ))


@router.post("/expenses/{expense_id}/edit", name="edit_expense")
async def edit_expense_submit(request: Request, expense_id: int):
    denied = require_permission(request, "expenses.write")
    if denied:
        return denied
    await csrf_protect(request)
    form = await request.form()
    modify_expense(
        expense_id=expense_id,
        date=str(form.get("date", "")).strip(),
        category=str(form.get("category", "general")).strip(),
        description=str(form.get("description", "")).strip(),
        amount=_parse_amount(form.get("amount")),
        method=str(form.get("payment_method", "cash")).strip(),
    )
    flash(request, "Dépense modifiée.", "success")
    return RedirectResponse("/expenses", status_code=303)


@router.post("/expenses/{expense_id}/delete", name="delete_expense")
async def delete_expense_route(request: Request, expense_id: int):
    denied = require_permission(request, "expenses.delete")
    if denied:
        return denied
    await csrf_protect(request)
    if remove_expense(expense_id):
        flash(request, "Dépense supprimée.", "success")
    else:
        flash(request, "Dépense introuvable.", "danger")
    return RedirectResponse("/expenses", status_code=303)
