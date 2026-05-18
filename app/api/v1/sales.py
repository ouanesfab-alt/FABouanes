from __future__ import annotations

from fastapi import APIRouter, Request
import asyncio


from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import (
    append_date_range,
    append_text_search,
    filtered_sellable_items,
    json_response,
    payload_to_form_data,
    query_db,
    query_list,

    query_list_async,
    sale_document_payload,
    sale_payload,

)
from app.core.permissions import PERMISSION_CATALOG_READ, PERMISSION_OPERATIONS_DELETE, PERMISSION_OPERATIONS_READ, PERMISSION_OPERATIONS_WRITE
from app.repositories.operation_repository import (
    list_recent_operations,
)
from app.repositories.sale_repository import (

    list_sales,
)
from app.services.sale_service import (

    create_sale_from_form,
    delete_sale_by_id,
    edit_sale_document_from_form,
    edit_sale_from_form,
)


router = APIRouter(prefix="/api/v1", tags=["sales"])


@router.get("/sellable-items")
async def api_sellable_items(request: Request):
    require_api_user(request, PERMISSION_CATALOG_READ)
    return json_response(await filtered_sellable_items(request))



@router.api_route("/sales", methods=["GET", "POST"])
async def api_sales(request: Request):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "POST" else PERMISSION_OPERATIONS_READ)
    if request.method == "POST":
        payload = await request.json()
        client_id = payload.get("client_id")
        if client_id:
            client_exists = await asyncio.to_thread(query_db, "SELECT id FROM clients WHERE id = %s", (client_id,), one=True)
            if not client_exists:
                api_error("not_found", f"Client introuvable (ID: {client_id})", 404)
        
        created = await asyncio.to_thread(create_sale_from_form, payload_to_form_data(payload))

        if created["mode"] == "line":
            payload = {
                "mode": "line",
                "kind": created["first_line_kind"],
                "sale": await asyncio.to_thread(sale_payload, created["first_line_kind"], int(created["first_line_id"])),

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

    rows, total = await list_sales(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        status=request.query_params.get("status"),
        page=int(request.query_params.get("page", 1)),
        page_size=int(request.query_params.get("page_size", 50))
    )
    
    meta = {
        "page": int(request.query_params.get("page", 1)),
        "page_size": int(request.query_params.get("page_size", 50)),
        "returned": len(rows),
        "total": total
    }
    return json_response(api_success(rows, meta))



@router.api_route("/sales/{kind}/{row_id}", methods=["GET", "PUT", "DELETE"])
async def api_sale_detail(request: Request, kind: str, row_id: int):
    permission = {
        "GET": PERMISSION_OPERATIONS_READ,
        "PUT": PERMISSION_OPERATIONS_WRITE,
        "DELETE": PERMISSION_OPERATIONS_DELETE,
    }[request.method]
    require_api_user(request, permission)
    sale = await asyncio.to_thread(sale_payload, kind, row_id)
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
            result = await asyncio.to_thread(edit_sale_from_form, kind, row_id, payload_to_form_data(await request.json()))
        except ValueError as exc:
            if "versements" in str(exc).lower():
                api_error("document_has_payments", str(exc), 409)
            api_error("sale_update_invalid", str(exc), 400)
        if result["mode"] == "document":
            return json_response(
                api_success(
                    {
                        "mode": "document",
                        "document_id": int(result["document_id"]),
                        "document": await asyncio.to_thread(sale_document_payload, int(result["document_id"])),
                    }
                )
            )
        sale = (await asyncio.to_thread(sale_payload, result["first_line_kind"], int(result["first_line_id"]))) or sale
    elif request.method == "DELETE":
        if not await asyncio.to_thread(delete_sale_by_id, kind, row_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    return json_response(api_success(sale))


@router.api_route("/sale-documents/{document_id}", methods=["GET", "PUT"])
async def api_sale_document_detail(request: Request, document_id: int):
    require_api_user(request, PERMISSION_OPERATIONS_WRITE if request.method == "PUT" else PERMISSION_OPERATIONS_READ)
    document = await asyncio.to_thread(sale_document_payload, document_id)
    if not document:
        api_error("not_found", "Facture introuvable.", 404)
    if request.method == "PUT":
        try:
            await asyncio.to_thread(edit_sale_document_from_form, document_id, payload_to_form_data(await request.json()))
        except ValueError as exc:
            if "versements" in str(exc).lower():
                api_error("document_has_payments", str(exc), 409, {"document_id": document_id})
            api_error("sale_document_invalid", str(exc), 400)
        document = await asyncio.to_thread(sale_document_payload, document_id)
    return json_response(api_success(document))



@router.get("/recent-operations")
async def api_recent_operations(request: Request):
    require_api_user(request, PERMISSION_OPERATIONS_READ)
    rows, total = await list_recent_operations(
        search=request.query_params.get("q"),
        date_from=request.query_params.get("date_from"),
        date_to=request.query_params.get("date_to"),
        kind=request.query_params.get("kind"),
        page=int(request.query_params.get("page", 1)),
        page_size=int(request.query_params.get("page_size", 50))
    )
    
    meta = {
        "page": int(request.query_params.get("page", 1)),
        "page_size": int(request.query_params.get("page_size", 50)),
        "returned": len(rows),
        "total": total
    }
    return json_response(api_success(rows, meta))

