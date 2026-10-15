"""Endpoints de synchronisation des opérations saisies hors-ligne."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, require_api_user
from app.core.async_db import get_async_session
from app.core.database import execute_db
from app.core.exceptions import ConflictError, ValidationError
from app.core.idempotency import check_idempotency, save_idempotency
from app.core.permissions import PERMISSION_OPERATIONS_WRITE
from app.core.rate_limit import limiter
from app.modules.production.schemas import ProductionBatchCreate
from app.infra.worker import enqueue_background_task
from app.modules.production.service import ProductionService
from app.modules.purchases.schemas import PurchaseFormSchema
from app.modules.purchases.service import PurchaseService
from app.modules.sales.schemas import SaleFormSchema
from app.modules.sales.service import SalesService
from app.modules.payments.service import create_payment_from_form

from app.core.uow import unit_of_work

logger = logging.getLogger("fabouanes.offline")
router = APIRouter(prefix="/api/mobile/v1/offline", tags=["offline"])


@router.post("/sync")
@limiter.limit("30/minute")
async def sync_operation(request: Request, db: AsyncSession = Depends(get_async_session)):
    """
    Reçoit une opération hors-ligne et l'exécute comme si elle venait du formulaire.
    Gère l'idempotence pour éviter les doublons lors des retries réseau.
    Retourne 200 si succès, 4xx si erreur métier, 5xx si erreur serveur.
    """
    require_api_user(request, PERMISSION_OPERATIONS_WRITE)
    body = await request.json()

    mutation_id = (
        request.headers.get("X-Idempotency-Key")
        or body.get("mutation_id")
        or (isinstance(body.get("payload"), dict) and body["payload"].get("mutation_id"))
        or body.get("idempotency_key")
        or body.get("key")
    )
    if mutation_id:
        cached_res = await check_idempotency(mutation_id, db=db)
        if cached_res is not None:
            return JSONResponse(cached_res["content"], status_code=cached_res.get("status_code", 200))

    op_type = body.get("type")
    payload = body.get("payload", {})

    # Check permission for purchase before try block
    if op_type == "create_purchase":
        require_api_user(request, "admin")

    try:
        if op_type == "create_sale":
            validated = SaleFormSchema(**payload)
            service = SalesService(db)
            result = await service.create_sale_from_form(validated)
            res_payload = {"ok": True, "mode": result.get("mode"), "mutation_id": mutation_id}
        elif op_type == "create_purchase":
            validated = PurchaseFormSchema(**payload)
            service = PurchaseService(db)
            result = await service.create_purchase_from_form(validated)
            res_payload = {"ok": True, "mode": result.get("mode"), "mutation_id": mutation_id}
        elif op_type == "create_payment":
            payment_id, payment_type = await create_payment_from_form(payload, db=db)
            res_payload = {"ok": True, "id": payment_id, "payment_type": payment_type, "mutation_id": mutation_id}
        elif op_type == "create_production":
            ProductionBatchCreate.model_validate(payload)
            service = ProductionService(db)
            result = await service.create_production(payload)
            res_payload = {"ok": True, "batch_id": result.get("batch_id"), "mutation_id": mutation_id}
        elif op_type == "create_expense":
            from app.modules.expenses.schemas import ExpenseCreateSchema
            from app.modules.expenses.service import add_expense

            exp_schema = ExpenseCreateSchema(**payload)
            expense_id = await add_expense(
                db,
                date=exp_schema.date,
                category=exp_schema.category,
                description=exp_schema.description or "",
                amount=exp_schema.amount,
                method=exp_schema.payment_method,
            )
            res_payload = {"ok": True, "expense_id": expense_id, "mutation_id": mutation_id}
        else:
            api_error("unknown_type", f"Type inconnu : {op_type}", 400)

        if mutation_id:
            await save_idempotency(mutation_id, {"content": res_payload, "status_code": 200}, db=db)
        return JSONResponse(res_payload)

    except HTTPException:
        raise
    except (ValueError, ValidationError, ConflictError) as exc:
        code = getattr(exc, "code", "validation_error")
        message = getattr(exc, "message", str(exc))
        api_error(code, message, 422)
    except Exception as exc:
        logger.exception("Offline sync operation failed")
        api_error("internal_error", "Erreur serveur", 500, details=str(exc))


@router.post("/sync/bulk")
@limiter.limit("30/minute")
async def sync_operations_bulk(request: Request, db: AsyncSession = Depends(get_async_session)):
    """
    Reçoit une liste d'opérations hors-ligne.
    Si 'staging' est vrai, écrit dans la table de staging et lance le worker en tâche de fond.
    Sinon, exécute chaque mutation individuellement dans un UoW dédié (Dead-Letter Queue).
    """
    require_api_user(request, PERMISSION_OPERATIONS_WRITE)
    body = await request.json()
    operations = body.get("operations") or []
    use_staging = body.get("staging") or False

    results = []

    if use_staging:
        for op in operations:
            op_type = op.get("type")
            payload = op.get("payload", {})
            mutation_id = (
                op.get("mutation_id")
                or (isinstance(payload, dict) and payload.get("mutation_id"))
                or op.get("idempotency_key")
                or op.get("key")
            )

            if mutation_id:
                cached_res = await check_idempotency(mutation_id)
                if cached_res is not None:
                    results.append(
                        {
                            "mutation_id": mutation_id,
                            "idempotency_key": mutation_id,
                            "status": "synced",
                            "status_code": cached_res.get("status_code", 200),
                            "response": cached_res.get("content", cached_res),
                        }
                    )
                    continue

            try:
                if op_type == "create_sale":
                    table_name = "offline_sales_staging"
                elif op_type == "create_payment":
                    table_name = "offline_payments_staging"
                else:
                    results.append(
                        {
                            "mutation_id": mutation_id,
                            "idempotency_key": mutation_id,
                            "status": "conflict",
                            "status_code": 400,
                            "response": {"error": f"Type d'opération inconnu pour staging : {op_type}"},
                        }
                    )
                    continue

                execute_db(
                    f"INSERT INTO {table_name} (idempotency_key, payload, status) VALUES (%s, %s, 'pending') ON CONFLICT DO NOTHING",
                    (mutation_id, json.dumps(payload)),
                )
                results.append(
                    {
                        "mutation_id": mutation_id,
                        "idempotency_key": mutation_id,
                        "status": "staged",
                        "status_code": 202,
                        "response": {"status": "staged"},
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "mutation_id": mutation_id,
                        "idempotency_key": mutation_id,
                        "status": "failed",
                        "status_code": 500,
                        "response": {"error": str(exc)},
                    }
                )

        await enqueue_background_task("process_offline_staging_task")
        return JSONResponse({"results": results})

    # Individual UoW execution path (per-mutation savepoint/uow isolation)
    for op in operations:
        op_type = op.get("type")
        payload = op.get("payload", {})
        mutation_id = (
            op.get("mutation_id")
            or (isinstance(payload, dict) and payload.get("mutation_id"))
            or op.get("idempotency_key")
            or op.get("key")
        )

        # 1. Check idempotency
        if mutation_id:
            cached_res = await check_idempotency(mutation_id)
            if cached_res is not None:
                results.append(
                    {
                        "mutation_id": mutation_id,
                        "idempotency_key": mutation_id,
                        "status": "synced",
                        "status_code": cached_res.get("status_code", 200),
                        "response": cached_res.get("content", cached_res),
                    }
                )
                continue

        # 2. Permission check for admin operations
        if op_type == "create_purchase":
            try:
                require_api_user(request, "admin")
            except HTTPException as he:
                results.append(
                    {
                        "mutation_id": mutation_id,
                        "idempotency_key": mutation_id,
                        "status": "conflict",
                        "status_code": he.status_code,
                        "error": str(he.detail),
                        "response": {"status": "conflict", "reason": str(he.detail)},
                    }
                )
                continue

        # 3. Process operation in dedicated Unit of Work
        try:
            async with unit_of_work() as op_db:
                if op_type == "create_sale":
                    validated = SaleFormSchema(**payload)
                    service = SalesService(op_db)
                    result = await service.create_sale_from_form(validated)
                    res_payload = {"ok": True, "mode": result.get("mode"), "mutation_id": mutation_id}
                elif op_type == "create_purchase":
                    validated = PurchaseFormSchema(**payload)
                    service = PurchaseService(op_db)
                    result = await service.create_purchase_from_form(validated)
                    res_payload = {"ok": True, "mode": result.get("mode"), "mutation_id": mutation_id}
                elif op_type == "create_payment":
                    payment_id, payment_type = await create_payment_from_form(payload, db=op_db)
                    res_payload = {
                        "ok": True,
                        "id": payment_id,
                        "payment_type": payment_type,
                        "mutation_id": mutation_id,
                    }
                elif op_type == "create_production":
                    ProductionBatchCreate.model_validate(payload)
                    service = ProductionService(op_db)
                    result = await service.create_production(payload)
                    res_payload = {"ok": True, "batch_id": result.get("batch_id"), "mutation_id": mutation_id}
                elif op_type == "create_expense":
                    from app.modules.expenses.schemas import ExpenseCreateSchema
                    from app.modules.expenses.service import add_expense

                    exp_schema = ExpenseCreateSchema(**payload)
                    expense_id = await add_expense(
                        op_db,
                        date=exp_schema.date,
                        category=exp_schema.category,
                        description=exp_schema.description or "",
                        amount=exp_schema.amount,
                        method=exp_schema.payment_method,
                    )
                    res_payload = {"ok": True, "expense_id": expense_id, "mutation_id": mutation_id}
                else:
                    results.append(
                        {
                            "mutation_id": mutation_id,
                            "idempotency_key": mutation_id,
                            "status": "conflict",
                            "status_code": 400,
                            "error": f"Type inconnu : {op_type}",
                            "response": {"status": "conflict", "reason": f"Type inconnu : {op_type}"},
                        }
                    )
                    continue

                # Save idempotency on success
                if mutation_id:
                    await save_idempotency(mutation_id, {"content": res_payload, "status_code": 200}, db=op_db)

            results.append(
                {
                    "mutation_id": mutation_id,
                    "idempotency_key": mutation_id,
                    "status": "synced",
                    "status_code": 200,
                    "response": res_payload,
                }
            )

        except HTTPException as he:
            logger.warning("HTTPException in bulk mutation %s: %s", mutation_id, he.detail)
            results.append(
                {
                    "mutation_id": mutation_id,
                    "idempotency_key": mutation_id,
                    "status": "conflict" if he.status_code < 500 else "failed",
                    "status_code": he.status_code,
                    "error": str(he.detail),
                    "response": {"status": "conflict" if he.status_code < 500 else "failed", "reason": str(he.detail)},
                }
            )
        except (ValueError, ValidationError, ConflictError) as exc:
            err_msg = str(exc)
            logger.warning("Business validation conflict in bulk mutation %s: %s", mutation_id, err_msg)
            results.append(
                {
                    "mutation_id": mutation_id,
                    "idempotency_key": mutation_id,
                    "status": "conflict",
                    "status_code": 422,
                    "error": err_msg,
                    "response": {"status": "conflict", "reason": err_msg},
                }
            )
        except Exception as exc:
            logger.exception("Bulk sync operation failed due to internal error on mutation %s", mutation_id)
            results.append(
                {
                    "mutation_id": mutation_id,
                    "idempotency_key": mutation_id,
                    "status": "failed",
                    "status_code": 500,
                    "error": str(exc),
                    "response": {"status": "failed", "error": "Erreur serveur", "details": str(exc)},
                }
            )

    return JSONResponse({"results": results})
