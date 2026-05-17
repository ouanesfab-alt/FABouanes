from __future__ import annotations

from fastapi import APIRouter, Request
import asyncio

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import (
    client_history_payload,
    client_payload,
    finished_product_payload,
    json_response,
    payload_to_form_data,
    raw_material_payload,
    supplier_payload,
)
from app.repositories.client_repository import list_clients
from app.repositories.supplier_repository import list_suppliers
from app.repositories.stock_repository import list_raw_materials, list_finished_products
from app.services.catalog_service import (
    create_catalog_item_from_form,
    delete_product_by_id,
    delete_raw_material_by_id,
    update_product_from_form,
    update_raw_material_from_form,
)
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import execute_db_async

from app.core.permissions import (
    PERMISSION_CATALOG_DELETE,
    PERMISSION_CATALOG_READ,
    PERMISSION_CATALOG_WRITE,
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
)
from app.services.client_service import create_client_from_form, update_client_from_form

router = APIRouter(prefix="/api/v1", tags=["contacts"])

@router.api_route("/clients", methods=["GET", "POST"])
async def api_clients(request: Request):
    require_api_user(request, PERMISSION_CONTACTS_WRITE if request.method == "POST" else PERMISSION_CONTACTS_READ)
    if request.method == "POST":
        payload = await request.json()
        client_id = await asyncio.to_thread(create_client_from_form, payload_to_form_data(payload))
        return json_response(api_success(await asyncio.to_thread(client_payload, client_id), status_code=201))

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_clients(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))

@router.api_route("/clients/{client_id}", methods=["GET", "PUT"])
async def api_client_detail(request: Request, client_id: int):
    require_api_user(request, PERMISSION_CONTACTS_WRITE if request.method == "PUT" else PERMISSION_CONTACTS_READ)
    client = await asyncio.to_thread(client_payload, client_id)
    if not client:
        api_error("not_found", "Client introuvable.", 404)
    if request.method == "PUT":
        payload = await request.json()
        await asyncio.to_thread(update_client_from_form, client_id, payload_to_form_data(payload))
        client = await asyncio.to_thread(client_payload, client_id)
    detail = await asyncio.to_thread(client_history_payload, client_id)
    client["summary"] = detail.get("stats", {}) if detail else {}
    return json_response(api_success(client))

@router.get("/clients/{client_id}/history")
async def api_client_history(request: Request, client_id: int):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    payload = await asyncio.to_thread(client_history_payload, client_id)
    if not payload:
        api_error("not_found", "Client introuvable.", 404)
    return json_response(api_success(payload))

@router.api_route("/suppliers", methods=["GET", "POST"])
async def api_suppliers(request: Request):
    require_api_user(request, PERMISSION_CONTACTS_WRITE if request.method == "POST" else PERMISSION_CONTACTS_READ)
    if request.method == "POST":
        payload = await request.json()
        supplier_id = await execute_db_async(
            "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
            (
                str(payload.get("name", "")).strip(),
                str(payload.get("phone", "")).strip(),
                str(payload.get("address", "")).strip(),
                str(payload.get("notes", "")).strip(),
            ),
        )
        supplier = await asyncio.to_thread(supplier_payload, supplier_id)
        audit_event("create_supplier", "supplier", supplier_id, source="api", after=supplier)
        log_activity("create_supplier", "supplier", supplier_id, str(payload.get("name", "")).strip())
        return json_response(api_success(supplier, status_code=201))

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_suppliers(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))

@router.api_route("/suppliers/{supplier_id}", methods=["GET", "PUT", "DELETE"])
async def api_supplier_detail(request: Request, supplier_id: int):
    permission = {
        "GET": PERMISSION_CONTACTS_READ,
        "PUT": PERMISSION_CONTACTS_WRITE,
        "DELETE": PERMISSION_CONTACTS_DELETE,
    }[request.method]
    require_api_user(request, permission)
    supplier = await asyncio.to_thread(supplier_payload, supplier_id)
    if not supplier:
        api_error("not_found", "Fournisseur introuvable.", 404)
    if request.method == "PUT":
        payload = await request.json()
        before = dict(supplier)
        await execute_db_async(
            "UPDATE suppliers SET name = ?, phone = ?, address = ?, notes = ? WHERE id = ?",
            (
                payload.get("name", supplier["name"]),
                payload.get("phone", supplier["phone"]),
                payload.get("address", supplier["address"]),
                payload.get("notes", supplier["notes"]),
                supplier_id,
            ),
        )
        supplier = await asyncio.to_thread(supplier_payload, supplier_id)
        audit_event("update_supplier", "supplier", supplier_id, source="api", before=before, after=supplier)
    elif request.method == "DELETE":
        before = dict(supplier)
        await execute_db_async("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        audit_event("delete_supplier", "supplier", supplier_id, source="api", before=before, after=None)
        return json_response(api_success({"deleted": True}))
    return json_response(api_success(supplier))

@router.api_route("/raw-materials", methods=["GET", "POST"])
async def api_raw_materials(request: Request):
    require_api_user(request, PERMISSION_CATALOG_WRITE if request.method == "POST" else PERMISSION_CATALOG_READ)
    if request.method == "POST":
        payload = dict(await request.json())
        payload["kind"] = "raw"
        _kind, material_id = await asyncio.to_thread(create_catalog_item_from_form, payload_to_form_data(payload))
        return json_response(api_success(await asyncio.to_thread(raw_material_payload, material_id), status_code=201))

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_raw_materials(
        search=request.query_params.get("q"),
        status=request.query_params.get("status"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))

@router.api_route("/raw-materials/{material_id}", methods=["GET", "PUT", "DELETE"])
async def api_raw_material_detail(request: Request, material_id: int):
    permission = {
        "GET": PERMISSION_CATALOG_READ,
        "PUT": PERMISSION_CATALOG_WRITE,
        "DELETE": PERMISSION_CATALOG_DELETE,
    }[request.method]
    require_api_user(request, permission)
    material = await asyncio.to_thread(raw_material_payload, material_id)
    if not material:
        api_error("not_found", "Matiere premiere introuvable.", 404)
    if request.method == "PUT":
        payload = dict(await request.json())
        await asyncio.to_thread(update_raw_material_from_form, material_id, payload_to_form_data(payload))
        material = await asyncio.to_thread(raw_material_payload, material_id)
    elif request.method == "DELETE":
        if not await asyncio.to_thread(delete_raw_material_by_id, material_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    return json_response(api_success(material))

@router.api_route("/finished-products", methods=["GET", "POST"])
async def api_finished_products(request: Request):
    require_api_user(request, PERMISSION_CATALOG_WRITE if request.method == "POST" else PERMISSION_CATALOG_READ)
    if request.method == "POST":
        payload = dict(await request.json())
        payload["kind"] = "finished"
        _kind, product_id = await asyncio.to_thread(create_catalog_item_from_form, payload_to_form_data(payload))
        return json_response(api_success(await asyncio.to_thread(finished_product_payload, product_id), status_code=201))

    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    rows, total = await list_finished_products(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    return json_response(api_success(rows, meta))

@router.api_route("/finished-products/{product_id}", methods=["GET", "PUT", "DELETE"])
async def api_finished_product_detail(request: Request, product_id: int):
    permission = {
        "GET": PERMISSION_CATALOG_READ,
        "PUT": PERMISSION_CATALOG_WRITE,
        "DELETE": PERMISSION_CATALOG_DELETE,
    }[request.method]
    require_api_user(request, permission)
    product = await asyncio.to_thread(finished_product_payload, product_id)
    if not product:
        api_error("not_found", "Produit fini introuvable.", 404)
    if request.method == "PUT":
        payload = dict(await request.json())
        await asyncio.to_thread(update_product_from_form, product_id, payload_to_form_data(payload))
        product = await asyncio.to_thread(finished_product_payload, product_id)
    elif request.method == "DELETE":
        if not await asyncio.to_thread(delete_product_by_id, product_id):
            api_error("conflict", "Suppression impossible.", 409)
        return json_response(api_success({"deleted": True}))
    return json_response(api_success(product))
