from __future__ import annotations

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
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
from app.core.db_access import execute_db_async, query_db


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
    rows, total = await list_clients.async_(
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

def _fetch_client_history(client_id: int, page: int, page_size: int) -> tuple[list, int]:
    # 1. Fetch all rows to calculate the running balance correctly across all pages
    rows = query_db(
        """
        SELECT
            id,
            operation_date,
            designation,
            montant_achat,
            montant_verse,
            solde_cumule,
            ordre_import,
            source,
            created_at
        FROM client_history
        WHERE client_id = %s
        ORDER BY
            CASE WHEN source = 'import_excel' THEN 0 ELSE 1 END,
            CASE WHEN source = 'import_excel' THEN ordre_import ELSE NULL END,
            CASE WHEN source = 'app'          THEN operation_date ELSE NULL END,
            CASE WHEN source = 'app'          THEN id             ELSE NULL END
        """,
        (client_id,),
    )
    
    total = len(rows)
    
    # 2. Calculate the running balance
    current_balance = 0.0
    processed_rows = []
    
    for r in rows:
        m_achat = float(r["montant_achat"] or 0)
        m_verse = float(r["montant_verse"] or 0)
        
        if r["source"] == "import_excel":
            current_balance = float(r["solde_cumule"] or 0)
            solde = current_balance
        else:
            current_balance = current_balance + m_achat - m_verse
            solde = current_balance
            
        designation = r["designation"] or ""
        ordre = r["ordre_import"] or 0
        if r["source"] == "import_excel" and ordre == 0 and "ancien" in designation.lower():
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
            "operation_date": str(r["operation_date"]),
            "designation": designation,
            "montant_achat": m_achat,
            "montant_verse": m_verse,
            "solde_cumule": round(solde, 2),
            "ordre_import": int(ordre),
            "source": r["source"],
            "type_operation": type_op,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
        
    # 3. Apply pagination in memory
    offset = (page - 1) * page_size
    paginated = processed_rows[offset : offset + page_size]
    
    return paginated, total


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
        from app.services.client_import_service import import_client_history_from_excel
        result = await asyncio.to_thread(
            import_client_history_from_excel,
            temp_path,
            client_id,
            force_reimport
        )
        log_activity(
            "import_client_history",
            "client",
            result["client_id"],
            f"Import historique client '{result['client_name']}' - {result['nb_lignes']} lignes, solde final: {result['solde_final']}"
        )
        return json_response(api_success(result))
    except Exception as e:
        api_error("bad_request", f"Erreur lors de l'import : {str(e)}", 400)
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.get("/clients/{client_id}/history")
async def api_client_history(
    request: Request,
    client_id: int,
    page: int = 1,
    page_size: int = 50,
):
    require_api_user(request, PERMISSION_CONTACTS_READ)
    client_exists = await asyncio.to_thread(query_db, "SELECT 1 FROM clients WHERE id = %s", (client_id,), True)
    if not client_exists:
        api_error("not_found", "Client introuvable.", 404)
        
    rows, total = await asyncio.to_thread(_fetch_client_history, client_id, page, page_size)
    import math
    total_pages = math.ceil(total / page_size) if page_size > 0 else 1
    
    return json_response(api_success({
        "client_id": client_id,
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }))


@router.api_route("/suppliers", methods=["GET", "POST"])
async def api_suppliers(request: Request):
    require_api_user(request, PERMISSION_CONTACTS_WRITE if request.method == "POST" else PERMISSION_CONTACTS_READ)
    if request.method == "POST":
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
            "UPDATE suppliers SET name = %s, phone = %s, address = %s, notes = %s WHERE id = %s",
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
        await execute_db_async("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
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


@router.post("/clients/import-history/bulk")
async def bulk_import_client_history(
    file: UploadFile = File(...),
):
    """
    Accepte un fichier ZIP contenant plusieurs .xlsx (un par client).
    Importe chaque fichier et retourne un rapport global.
    """
    # Choix importants :
    # 1. Utilisation de zipfile pour extraire dynamiquement les fichiers Excel en mémoire/dossier temporaire.
    # 2. Appel asynchrone sécurisé de import_client_history_from_excel dans un thread séparé.
    import tempfile, zipfile, os
    from app.services.client_import_service import (
        import_client_history_from_excel
    )

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
                        rapport = await asyncio.to_thread(
                            import_client_history_from_excel,
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


@router.get("/clients/export")
async def export_clients_csv():
    """
    Exporte tous les clients avec solde, total achats, total versements,
    dernière opération. Format CSV téléchargeable.
    """
    # Choix importants :
    # 1. Requête SQL pure optimisée avec agrégations pour éviter les requêtes par lot.
    # 2. Utilisation de Response de FastAPI pour renvoyer des données binaires (CSV encodé UTF-8 avec BOM pour Excel).
    import csv, io
    from datetime import date
    from fastapi import Response

    def _build_export():
        rows = query_db("""
            SELECT
                c.id, c.name,
                c.balance,
                (COALESCE((SELECT SUM(s.total) FROM sales s WHERE s.client_id = c.id), 0) +
                 COALESCE((SELECT SUM(rs.total) FROM raw_sales rs WHERE rs.client_id = c.id), 0)) AS total_achats,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.client_id = c.id), 0) AS total_verses,
                (SELECT MAX(d) FROM (
                    SELECT MAX(sale_date) AS d FROM sales WHERE client_id = c.id
                    UNION ALL
                    SELECT MAX(sale_date) AS d FROM raw_sales WHERE client_id = c.id
                 ) t) AS derniere_vente,
                (SELECT MAX(payment_date) FROM payments WHERE client_id = c.id) AS dernier_paiement
            FROM clients c
            ORDER BY c.balance DESC
        """)
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

    csv_content = await asyncio.to_thread(_build_export)
    filename = f"clients_export_{date.today().isoformat()}.csv"
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

