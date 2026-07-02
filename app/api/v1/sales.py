from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import (
    filtered_sellable_items,
    json_response,
    sale_document_payload,
    sale_payload,
    add_cache_headers,
)
from app.core.permissions import PERMISSION_CATALOG_READ, PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.modules.reports.repository import list_recent_operations
# list_sales is now handled via SalesService
from app.core.async_db import get_async_session
from app.modules.sales.service import SalesService
from app.modules.sales.schemas_validation import SaleFormSchema



router = APIRouter(prefix="/api/v1", tags=["sales"])


@router.get("/sellable-items")
async def api_sellable_items(request: Request):
    require_api_user(request, PERMISSION_CATALOG_READ)
    res_data = await filtered_sellable_items(request)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response



@router.api_route("/sales", methods=["GET", "POST"])
async def api_sales(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "POST" else PERMISSION_OPERATIONS_READ)
    if request.method == "POST":
        payload = await request.json()
        validated = SaleFormSchema(**payload)
        service = SalesService(db)
        created = await service.create_sale_from_form(validated)

        if created["mode"] == "line":
            payload = {
                "mode": "line",
                "kind": created["first_line_kind"],
                "sale": await sale_payload(created["first_line_kind"], int(created["first_line_id"])),
            }
        else:
            payload = {
                "mode": "document",
                "document_id": int(created["document_id"]),
                "line_count": int(created["line_count"]),
                "print_doc_type": created["print_doc_type"],
                "print_item_id": int(created["print_item_id"]),
            }
        return json_response(api_success(payload, status_code=201))

    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    service = SalesService(db)
    rows, total = await service.list_sales(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        status=request.query_params.get("status"),
        page=page,
        page_size=page_size
    )
    
    meta = {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response



@router.api_route("/sales/{kind}/{row_id}", methods=["GET", "PUT", "DELETE"])
async def api_sale_detail(request: Request, kind: str, row_id: int, db: AsyncSession = Depends(get_async_session)):
    permission = {
        "GET": PERMISSION_OPERATIONS_READ,
        "PUT": PERMISSION_OPERATIONS_WRITE,
        "DELETE": PERMISSION_OPERATIONS_DELETE,
    }[request.method]
    require_api_user(request, permission)
    sale = await sale_payload(kind, row_id)
    if not sale:
        api_error("not_found", "Vente introuvable.", 404)
    if request.method == "PUT":
        if sale.get("document_id"):
            api_error(
                "document_edit_required",
                "Cette ligne appartient deja a une facture multi-lignes.",
                409,
                {"document_id": int(sale["document_id"])},
            )
        try:
            payload = await request.json()
            validated = SaleFormSchema(**payload)
            service = SalesService(db)
            result = await service.edit_sale_from_form(kind, row_id, validated)
        except Exception as exc:
            msg = str(exc)
            if "versements" in msg.lower():
                api_error("document_has_payments", msg, 409)
            api_error("sale_update_invalid", msg, 400)
        if result["mode"] == "document":
            return json_response(
                api_success(
                    {
                        "mode": "document",
                        "document_id": int(result["document_id"]),
                        "document": await sale_document_payload(int(result["document_id"])),
                    }
                )
            )
        sale = (await sale_payload(result["first_line_kind"], int(result["first_line_id"]))) or sale
    elif request.method == "DELETE":
        service = SalesService(db)
        if not await service.delete_sale_by_id(kind, row_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    res_data = api_success(sale)
    response = json_response(res_data)
    if request.method == "GET":
        add_cache_headers(request, response, res_data, max_age=30)
    return response


@router.api_route("/sale-documents/{document_id}", methods=["GET", "PUT"])
async def api_sale_document_detail(request: Request, document_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "PUT" else PERMISSION_OPERATIONS_READ)
    document = await sale_document_payload(document_id)
    if not document:
        api_error("not_found", "Facture introuvable.", 404)
    if request.method == "PUT":
        try:
            payload = await request.json()
            validated = SaleFormSchema(**payload)
            service = SalesService(db)
            await service.edit_sale_document_from_form(document_id, validated)
        except Exception as exc:
            msg = str(exc)
            if "versements" in msg.lower():
                api_error("document_has_payments", msg, 409, {"document_id": document_id})
            api_error("sale_document_invalid", msg, 400)
        document = await sale_document_payload(document_id)
    res_data = api_success(document)
    response = json_response(res_data)
    if request.method == "GET":
        add_cache_headers(request, response, res_data, max_age=30)
    return response



@router.get("/recent-operations")
async def api_recent_operations(request: Request):
    require_api_user(request, PERMISSION_OPERATIONS_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    rows, total = await list_recent_operations(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        page=page,
        page_size=page_size
    )
    
    meta = {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total
    }
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response

