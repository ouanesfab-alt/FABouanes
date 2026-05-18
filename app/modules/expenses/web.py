"""Routes web du module Dépenses & Charges, avec validation Pydantic."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.modules.expenses.service import (
    add_expense, get_categories, get_expense, get_payment_methods,
    list_expenses, modify_expense, remove_expense,
)
from app.modules.expenses.repository import expenses_by_category
from app.modules.expenses.schemas_validation import ExpenseCreateSchema
from app.web.deps import csrf_protect, flash, require_permission, template_context, templates

router = APIRouter()


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
    
    try:
        data = ExpenseCreateSchema(
            date=form.get("date"),
            category=form.get("category"),
            description=form.get("description"),
            amount=form.get("amount"),
            payment_method=form.get("payment_method"),
        )
    except ValidationError as e:
        for err in e.errors():
            msg = f"Erreur de validation : {err['loc'][0]} - {err['msg']}"
            flash(request, msg, "danger")
        return templates.TemplateResponse("expense_form.html", template_context(
            request, expense=form, categories=get_categories(),
            payment_methods=get_payment_methods(), title="Nouvelle dépense",
        ))
        
    add_expense(
        date=data.date.isoformat(),
        category=data.category,
        description=data.description,
        amount=data.amount,
        method=data.payment_method,
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
    
    expense = get_expense(expense_id)
    if not expense:
        flash(request, "Dépense introuvable.", "danger")
        return RedirectResponse("/expenses", status_code=303)
        
    form = await request.form()
    try:
        data = ExpenseCreateSchema(
            date=form.get("date"),
            category=form.get("category"),
            description=form.get("description"),
            amount=form.get("amount"),
            payment_method=form.get("payment_method"),
        )
    except ValidationError as e:
        for err in e.errors():
            msg = f"Erreur de validation : {err['loc'][0]} - {err['msg']}"
            flash(request, msg, "danger")
        form_dict = dict(form)
        form_dict["id"] = expense_id
        return templates.TemplateResponse("expense_form.html", template_context(
            request, expense=form_dict, categories=get_categories(),
            payment_methods=get_payment_methods(), title="Modifier la dépense",
        ))
        
    modify_expense(
        expense_id=expense_id,
        date=data.date.isoformat(),
        category=data.category,
        description=data.description,
        amount=data.amount,
        method=data.payment_method,
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
