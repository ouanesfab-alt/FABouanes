from __future__ import annotations

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Response, Depends
import asyncio
from sqlalchemy import select, union_all, func, case, literal_column, text, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_error, api_success, require_api_user
from app.api.v1._common import (
    client_history_payload,
    client_payload,
    finished_product_payload,
    json_response,
    payload_to_form_data,
    raw_material_payload,
    supplier_payload,
    add_cache_headers,
)
from app.repositories.supplier_repository import list_suppliers
from app.repositories.stock_repository import list_raw_materials, list_finished_products
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.db_access import execute_db_async, query_db_async
from app.core.async_db import get_async_session
from app.core.models import Client, ClientHistory, Sale, RawSale, Payment

from app.modules.clients.service import ClientService
from app.modules.clients.schemas_validation import ClientCreateSchema, ClientUpdateSchema
from app.modules.catalog.service import CatalogService
from app.modules.catalog.schemas_validation import (
    RawMaterialCreateSchema,
    RawMaterialUpdateSchema,
    FinishedProductCreateSchema,
    FinishedProductUpdateSchema,
)

from app.core.permissions import (
    PERMISSION_CATALOG_DELETE,
    PERMISSION_CATALOG_READ,
    PERMISSION_CATALOG_WRITE,
    PERMISSION_CONTACTS_DELETE,
    PERMISSION_CONTACTS_READ,
    PERMISSION_CONTACTS_WRITE,
)

router = APIRouter(prefix="/api/v1", tags=["contacts"])

@router.get("/clients")
async def api_get_clients(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    service = ClientService(db)
    rows, total = await service.list_clients_with_stats(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.post("/clients")
async def api_create_client(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    payload = await request.json()
    validated = ClientCreateSchema(**payload)
    service = ClientService(db)
    client = await service.create_client(validated)
    return json_response(api_success(await client_payload(client.id), status_code=201))

@router.get("/clients/export")
async def export_clients_csv(request: Request, db: AsyncSession = Depends(get_async_session)):
    """
    Exporte tous les clients avec solde, total achats, total versements,
    dernière opération. Format CSV téléchargeable.
    """
    require_api_user(request, PERMISSION_CONTACTS_READ)
    import csv, io
    from datetime import date
    async def _build_export():
        sub_sales = select(func.max(Sale.sale_date).label("d")).where(Sale.client_id == Client.id)
        sub_raw_sales = select(func.max(RawSale.sale_date).label("d")).where(RawSale.client_id == Client.id)
        union_sales = union_all(sub_sales, sub_raw_sales).subquery()
        derniere_vente_expr = select(func.max(union_sales.c.d)).scalar_subquery()

        dernier_paiement_expr = select(func.max(Payment.payment_date)).where(Payment.client_id == Client.id).scalar_subquery()

        stmt = select(
            literal_column("id"),
            literal_column("name"),
            literal_column("current_balance").label("balance"),
            literal_column("total_sales").label("total_achats"),
            literal_column("total_payments").label("total_verses"),
            derniere_vente_expr.label("derniere_vente"),
            dernier_paiement_expr.label("dernier_paiement")
        ).select_from(table("clients_with_stats").alias("c")).order_by(literal_column("current_balance").desc())
        
        res = await db.execute(stmt)
        rows = [dict(row._mapping) for row in res.fetchall()]
        
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=[
            "id", "nom", "solde_actuel",
            "total_achats", "total_versements",
            "derniere_vente", "dernier_paiement",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "id": row["id"],
                "nom": row["name"],
                "solde_actuel": row["balance"],
                "total_achats": row["total_achats"],
                "total_versements": row["total_verses"],
                "derniere_vente": row["derniere_vente"] or "",
                "dernier_paiement": row["dernier_paiement"] or "",
            })
        return buf.getvalue()

    csv_content = await _build_export()
    filename = f"clients_export_{date.today().isoformat()}.csv"
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/clients/{client_id}")
async def api_get_client_detail(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    client = await client_payload(client_id)
    if not client:
        api_error("not_found", "Client introuvable.", 404)
    detail = await client_history_payload(client_id, db)
    client["summary"] = detail.get("stats", {}) if detail else {}
    res_data = api_success(client)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.put("/clients/{client_id}")
async def api_update_client(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    client = await client_payload(client_id)
    if not client:
        api_error("not_found", "Client introuvable.", 404)
    payload = await request.json()
    validated = ClientUpdateSchema(**payload)
    service = ClientService(db)
    await service.update_client(client_id, validated)
    client = await client_payload(client_id)
    detail = await client_history_payload(client_id, db)
    client["summary"] = detail.get("stats", {}) if detail else {}
    return json_response(api_success(client))

@router.post("/clients/{client_id}/shred")
async def api_shred_client(request: Request, client_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CONTACTS_DELETE)
    service = ClientService(db)
    client = await service.get_client(client_id)
    if not client:
        api_error("not_found", "Client introuvable.", 404)
    before_dump = client.model_dump()
    success = await service.shred_client(client_id)
    if not success:
        api_error("bad_request", "Erreur lors de l'anonymisation.", 400)
    after_client = await service.get_client(client_id)
    log_activity("shred_client", "client", client_id, client.name)
    audit_event("shred_client", "client", client_id, before=before_dump, after=after_client.model_dump() if after_client else None)
    return json_response(api_success({"shredded": True}))

async def _fetch_client_history(client_id: int, page: int, page_size: int, db: AsyncSession) -> tuple[list, int]:
    # 1. Fetch total count first
    count_stmt = select(func.count(ClientHistory.id)).where(ClientHistory.client_id == client_id)
    total = (await db.execute(count_stmt)).scalar_one()
    if total == 0:
        return [], 0

    # 2. Fetch only the paginated slice
    offset = (page - 1) * page_size
    stmt = select(ClientHistory).where(ClientHistory.client_id == client_id).order_by(
        case((ClientHistory.source == 'import_excel', 0), else_=1),
        case((ClientHistory.source == 'import_excel', ClientHistory.ordre_import), else_=None),
        case((ClientHistory.source == 'app', ClientHistory.operation_date), else_=None),
        case((ClientHistory.source == 'app', ClientHistory.id), else_=None)
    ).offset(offset).limit(page_size)
    
    res = await db.execute(stmt)
    rows = res.scalars().all()
    
    # 3. Process only the paginated rows
    processed_rows = []
    
    for r in rows:
        m_achat = float(r.montant_achat or 0)
        m_verse = float(r.montant_verse or 0)
        solde = float(r.solde_cumule or 0)
            
        designation = r.designation or ""
        ordre = r.ordre_import or 0
        if r.source == "import_excel" and ordre == 0 and "ancien" in designation.lower():
            type_op = "ouverture"
        elif m_achat > 0 and m_verse == 0:
            type_op = "achat"
        elif m_achat == 0 and m_verse > 0:
            type_op = "versement"
        elif m_achat > 0 and m_verse > 0:
            if abs(m_achat - m_verse) < 0.01:
                type_op = "immediat"
            else:
                type_op = "mixte"
        else:
            type_op = "achat"
            
        processed_rows.append({
            "operation_date": str(r.operation_date),
            "designation": designation,
            "montant_achat": m_achat,
            "montant_verse": m_verse,
            "solde_cumule": round(solde, 2),
            "ordre_import": int(ordre),
            "source": r.source,
            "type_operation": type_op,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
        
    return processed_rows, total


@router.post("/clients/import-history")
async def import_client_history(
    request: Request,
    file: UploadFile = File(...),
    client_id: int | None = Form(None),
    force_reimport: bool = Form(True),
):
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    import tempfile
    import os
    
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        temp_path = tmp.name

    try:
        from app.core.worker import enqueue_background_task
        job_id = await enqueue_background_task(
            "import_excel_task",
            temp_path,
            client_id,
            force_reimport
        )
        return json_response(api_success({
            "task_id": job_id,
            "status": "enqueued",
            "message": "L'importation de l'historique a été lancée en arrière-plan."
        }))
    except Exception as e:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        api_error("bad_request", f"Erreur lors du lancement de l'import : {str(e)}", 400)


@router.get("/clients/{client_id}/history")
async def api_client_history(
    request: Request,
    client_id: int,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_async_session)
):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    client_exists = (await db.execute(select(1).select_from(Client).where(Client.id == client_id))).scalar()
    if not client_exists:
        api_error("not_found", "Client introuvable.", 404)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rows, total = await _fetch_client_history(client_id, page, page_size, db)
    import math
    total_pages = math.ceil(total / page_size) if page_size > 0 else 1
    
    res_data = api_success({
        "client_id": client_id,
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    })
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=30)
    return response


@router.get("/suppliers")
async def api_get_suppliers(request: Request):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    rows, total = await list_suppliers(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.post("/suppliers")
async def api_create_supplier(request: Request):
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    payload = await request.json()
    supplier_id = await execute_db_async(
        "INSERT INTO suppliers (name, phone, address, notes) VALUES (%s, %s, %s, %s)",
        (
            str(payload.get("name", "")).strip(),
            str(payload.get("phone", "")).strip(),
            str(payload.get("address", "")).strip(),
            str(payload.get("notes", "")).strip(),
        ),
    )
    supplier = await supplier_payload(supplier_id)
    audit_event("create_supplier", "supplier", supplier_id, source="api", after=supplier)
    log_activity("create_supplier", "supplier", supplier_id, str(payload.get("name", "")).strip())
    return json_response(api_success(supplier, status_code=201))

@router.get("/suppliers/{supplier_id}")
async def api_get_supplier_detail(request: Request, supplier_id: int):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    supplier = await supplier_payload(supplier_id)
    if not supplier:
        api_error("not_found", "Fournisseur introuvable.", 404)
    res_data = api_success(supplier)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.put("/suppliers/{supplier_id}")
async def api_update_supplier(request: Request, supplier_id: int):
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    supplier = await supplier_payload(supplier_id)
    if not supplier:
        api_error("not_found", "Fournisseur introuvable.", 404)
    payload = await request.json()
    before = dict(supplier)
    await execute_db_async(
        "UPDATE suppliers SET name = %s, phone = %s, address = %s, notes = %s WHERE id = %s",
        (
            payload.get("name", supplier["name"]),
            payload.get("phone", supplier["phone"]),
            payload.get("address", supplier["address"]),
            payload.get("notes", supplier["notes"]),
            supplier_id,
        ),
    )
    supplier = await supplier_payload(supplier_id)
    audit_event("update_supplier", "supplier", supplier_id, source="api", before=before, after=supplier)
    return json_response(api_success(supplier))

@router.delete("/suppliers/{supplier_id}")
async def api_delete_supplier(request: Request, supplier_id: int):
    require_api_user(request, PERMISSION_CONTACTS_DELETE)
    supplier = await supplier_payload(supplier_id)
    if not supplier:
        api_error("not_found", "Fournisseur introuvable.", 404)
    before = dict(supplier)
    await execute_db_async("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
    audit_event("delete_supplier", "supplier", supplier_id, source="api", before=before, after=None)
    return json_response(api_success({"deleted": True}))

@router.get("/raw-materials")
async def api_get_raw_materials(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    rows, total = await list_raw_materials(
        search=request.query_params.get("q"),
        status=request.query_params.get("status"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.post("/raw-materials")
async def api_create_raw_material(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    payload = dict(await request.json())
    validated = RawMaterialCreateSchema(**payload)
    service = CatalogService(db)
    material = await service.create_raw_material(validated)
    return json_response(api_success(await raw_material_payload(material.id), status_code=201))

@router.get("/raw-materials/{material_id}")
async def api_get_raw_material_detail(request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_READ)
    material = await raw_material_payload(material_id)
    if not material:
        api_error("not_found", "Matiere premiere introuvable.", 404)
    res_data = api_success(material)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.put("/raw-materials/{material_id}")
async def api_update_raw_material(request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    material = await raw_material_payload(material_id)
    if not material:
        api_error("not_found", "Matiere premiere introuvable.", 404)
    payload = dict(await request.json())
    validated = RawMaterialUpdateSchema(**payload)
    service = CatalogService(db)
    await service.update_raw_material(material_id, validated)
    material = await raw_material_payload(material_id)
    return json_response(api_success(material))

@router.delete("/raw-materials/{material_id}")
async def api_delete_raw_material(request: Request, material_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_DELETE)
    material = await raw_material_payload(material_id)
    if not material:
        api_error("not_found", "Matiere premiere introuvable.", 404)
    service = CatalogService(db)
    if not await service.delete_raw_material(material_id):
        api_error("conflict", "Suppression impossible.", 409)
    return json_response(api_success({"deleted": True}))

@router.get("/finished-products")
async def api_get_finished_products(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_READ)
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    rows, total = await list_finished_products(
        search=request.query_params.get("q"),
        page=page,
        page_size=page_size
    )
    meta = {"page": page, "page_size": page_size, "returned": len(rows), "total": total}
    res_data = api_success(rows, meta)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.post("/finished-products")
async def api_create_finished_product(request: Request, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    payload = dict(await request.json())
    validated = FinishedProductCreateSchema(**payload)
    service = CatalogService(db)
    product = await service.create_finished_product(validated)
    return json_response(api_success(await finished_product_payload(product.id), status_code=201))

@router.get("/finished-products/{product_id}")
async def api_get_finished_product_detail(request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_READ)
    product = await finished_product_payload(product_id)
    if not product:
        api_error("not_found", "Produit fini introuvable.", 404)
    res_data = api_success(product)
    response = json_response(res_data)
    add_cache_headers(request, response, res_data, max_age=300)
    return response

@router.put("/finished-products/{product_id}")
async def api_update_finished_product(request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_WRITE)
    product = await finished_product_payload(product_id)
    if not product:
        api_error("not_found", "Produit fini introuvable.", 404)
    payload = dict(await request.json())
    validated = FinishedProductUpdateSchema(**payload)
    service = CatalogService(db)
    await service.update_finished_product(product_id, validated)
    product = await finished_product_payload(product_id)
    return json_response(api_success(product))

@router.delete("/finished-products/{product_id}")
async def api_delete_finished_product(request: Request, product_id: int, db: AsyncSession = Depends(get_async_session)):
    require_api_user(request, PERMISSION_CATALOG_DELETE)
    product = await finished_product_payload(product_id)
    if not product:
        api_error("not_found", "Produit fini introuvable.", 404)
    service = CatalogService(db)
    if not await service.delete_finished_product(product_id):
        api_error("conflict", "Suppression impossible.", 409)
    return json_response(api_success({"deleted": True}))


@router.post("/clients/import-history/bulk")
async def bulk_import_client_history(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Accepte un fichier ZIP contenant plusieurs .xlsx (un par client).
    Importe chaque fichier et retourne un rapport global.
    """
    require_api_user(request, PERMISSION_CONTACTS_WRITE)
    import tempfile, zipfile, os

    # Enforce a strict 50MB file size limit for ZIP uploads
    MAX_SIZE = 50 * 1024 * 1024
    if file.size is not None and file.size > MAX_SIZE:
        raise HTTPException(400, "Le fichier est trop volumineux (max 50 Mo)")

    results = []
    errors = []

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "upload.zip")
        total_size = 0
        with open(zip_path, "wb") as f:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > MAX_SIZE:
                    raise HTTPException(400, "Le fichier est trop volumineux (max 50 Mo)")
                f.write(chunk)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                xlsx_files = [
                    name for name in zf.namelist()
                    if name.lower().endswith(".xlsx")
                    and not name.startswith("__MACOSX")
                ]
                if not xlsx_files:
                    raise HTTPException(400,
                        "Aucun fichier .xlsx trouvé dans le ZIP")

                for xlsx_name in xlsx_files:
                    extracted = os.path.join(tmpdir, xlsx_name)
                    zf.extract(xlsx_name, tmpdir)
                    try:
                        service = ClientService(db)
                        rapport = await service.import_client_history_from_excel(
                            extracted, None, True
                        )
                        results.append(rapport)
                    except Exception as e:
                        errors.append({
                            "fichier": xlsx_name,
                            "erreur": str(e)
                        })
        except zipfile.BadZipFile:
            raise HTTPException(400, "Fichier ZIP invalide ou corrompu")

    return {
        "success": len(errors) == 0,
        "importes": len(results),
        "erreurs": len(errors),
        "detail_succes": results,
        "detail_erreurs": errors,
    }




