from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import json_response, purchase_document_payload, purchase_payload, add_cache_headers
from app.repositories.purchase_repository import list_purchases


from app.core.permissions import PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.core.async_db import get_async_session
from app.modules.purchases.service import PurchaseService
from app.modules.purchases.schemas_validation import PurchaseFormSchema


router = APIRouter(prefix="/api/v1", tags=["purchases"])


@router.api_route("/purchases", methods=["GET", "POST"])
async def api_purchases(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "POST" else PERMISSION_OPERATIONS_READ)
    if request.method == "POST":
        payload = await request.json()
        validated = PurchaseFormSchema(**payload)
        service = PurchaseService(db)
        created = await service.create_purchase_from_form(validated)
        if created["mode"] == "line":
            payload = {"mode": "line", "purchase": await purchase_payload(int(created["print_item_id"]))}
        else:
            payload = {
                "mode": "document",
                "document_id": int(created["document_id"]),
                "line_count": int(created["line_count"]),
                "print_doc_type": created["print_doc_type"],
                "print_item_id": int(created["print_item_id"]),
            }
        return json_response(api_success(payload, status_code=201))

    rows, total = await list_purchases(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        page=int(request.query_params.get("page", 1)),
        page_size=int(request.query_params.get("page_size", 50))
    )
    
    meta = {
        "page": int(request.query_params.get("page", 1)),
        "page_size": int(request.query_params.get("page_size", 50)),
        "returned": len(rows),
        "total": total
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response



@router.api_route("/purchases/{purchase_id}", methods=["GET", "PUT", "DELETE"])
async def api_purchase_detail(request: Request, purchase_id: int, db: AsyncSession = Depends(get_async_session)):
    permission = {
        "GET": PERMISSION_OPERATIONS_READ,
        "PUT": PERMISSION_OPERATIONS_WRITE,
        "DELETE": PERMISSION_OPERATIONS_DELETE,
    }[request.method]
    require_api_user(request, permission)
    purchase = await purchase_payload(purchase_id)
    if not purchase:
        api_error("not_found", "Achat introuvable.", 404)
    if request.method == "PUT":
        if purchase.get("document_id"):
            api_error(
                "document_edit_required",
                "Cette ligne appartient deja a un bon multi-lignes.",
                409,
                {"document_id": int(purchase["document_id"])},
            )
        try:
            payload = await request.json()
            validated = PurchaseFormSchema(**payload)
            service = PurchaseService(db)
            result = await service.edit_purchase_from_form(purchase_id, validated)
        except Exception as exc:
            api_error("purchase_update_invalid", str(exc), 400)
        if result["mode"] == "document":
            return json_response(
                api_success(
                    {
                        "mode": "document",
                        "document_id": int(result["document_id"]),
                        "document": await purchase_document_payload(int(result["document_id"])),
                    }
                )
            )
        purchase = await purchase_payload(int(result["print_item_id"]))
    elif request.method == "DELETE":
        service = PurchaseService(db)
        if not await service.delete_purchase_by_id(purchase_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    res_data = api_success(purchase)
    response = json_response(res_data)
    if request.method == "GET":
        add_cache_headers(request, response, res_data, max_age=30)
    return response



@router.api_route("/purchase-documents/{document_id}", methods=["GET", "PUT"])
async def api_purchase_document_detail(request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "PUT" else PERMISSION_OPERATIONS_READ)
    document = await purchase_document_payload(document_id)
    if not document:
        api_error("not_found", "Bon d'achat introuvable.", 404)
    if request.method == "PUT":
        try:
            payload = await request.json()
            validated = PurchaseFormSchema(**payload)
            service = PurchaseService(db)
            await service.edit_purchase_document_from_form(document_id, validated)
        except Exception as exc:
            api_error("purchase_document_invalid", str(exc), 400)
        document = await purchase_document_payload(document_id)
    res_data = api_success(document)
    response = json_response(res_data)
    if request.method == "GET":
        add_cache_headers(request, response, res_data, max_age=30)
    return response

