from __future__ import annotations

# NOTE: Ces fonctions sont intentionnellement synchrones.
# Toutes les routes API de FastAPI qui les appellent doivent le faire
# via asyncio.to_thread(la_fonction, *args, **kwargs) pour éviter de bloquer l'event loop.

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.api.deps import api_success
from app.core.db_access import query_db
from app.repositories.sale_repository import build_sellable_items
from app.services.client_service import get_client_detail_context
from app.services.purchase_service import get_purchase_document_context
from app.services.sale_service import get_sale_document_context

def json_response(payload: dict[str, Any]) -> JSONResponse:
    status_code = int(payload.pop("_status_code", 200))
    return JSONResponse(jsonable_encoder(payload), status_code=status_code)

def client_payload(client_id: int):
    row = query_db(
        "SELECT * FROM clients_with_stats WHERE id = %s",
        (client_id,),
        one=True,
    )
    return dict(row) if row else None

def supplier_payload(supplier_id: int):
    row = query_db("SELECT * FROM suppliers WHERE id = %s", (supplier_id,), one=True)
    return dict(row) if row else None

def raw_material_payload(material_id: int):
    row = query_db(
        """
        SELECT *,
               CASE WHEN stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold) THEN 1 ELSE 0 END AS is_low_stock,
               'raw' AS item_type
        FROM raw_materials
        WHERE id = %s
        """,
        (material_id,),
        one=True,
    )
    return dict(row) if row else None

def finished_product_payload(product_id: int):
    row = query_db(
        """
        SELECT *, 'finished' AS item_type
        FROM finished_products
        WHERE id = %s
        """,
        (product_id,),
        one=True,
    )
    return dict(row) if row else None

def production_payload(batch_id: int):
    row = query_db(
        """
        SELECT pb.*, fp.name AS product_name, fp.default_unit AS product_unit
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        WHERE pb.id = %s
        """,
        (batch_id,),
        one=True,
    )
    return dict(row) if row else None

def purchase_payload(purchase_id: int):
    row = query_db(
        """
        SELECT p.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name, r.name AS material_name, r.unit AS material_unit
        FROM purchases p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.id = %s
        """,
        (purchase_id,),
        one=True,
    )
    return dict(row) if row else None

def sale_payload(kind: str, row_id: int):
    if kind == "finished":
        row = query_db(
            """
            SELECT s.*, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                   'Produit fini' AS item_kind, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.id = %s
            """,
            (row_id,),
            one=True,
        )
    else:
        row = query_db(
            """
            SELECT rs.*, COALESCE(c.name, 'Comptoir') AS client_name, r.name AS item_name,
                   'Matiere premiere' AS item_kind, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.id = %s
            """,
            (row_id,),
            one=True,
        )
    return dict(row) if row else None

def purchase_document_payload(document_id: int):
    context = get_purchase_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["purchase_document"]),
        "lines": [dict(line) for line in context["purchase_lines"]],
        "line_count": len(context["purchase_lines"]),
    }

def sale_document_payload(document_id: int):
    context = get_sale_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["sale_document"]),
        "lines": [dict(line) for line in context["sale_lines"]],
        "line_count": len(context["sale_lines"]),
        "has_linked_payments": bool(context["has_linked_payments"]),
    }

def payment_payload(payment_id: int):
    row = query_db(
        """
        SELECT p.*, c.name AS client_name,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'finished:' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'raw:' || p.raw_sale_id
                   ELSE ''
               END AS sale_link,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matiere #' || p.raw_sale_id
                   ELSE '-'
               END AS sale_ref
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        WHERE p.id = %s
        """,
        (payment_id,),
        one=True,
    )
    return dict(row) if row else None

def client_history_payload(client_id: int):
    detail_context = get_client_detail_context(client_id)
    if not detail_context:
        return None
    return {
        "client": client_payload(client_id),
        "history": detail_context.get("timeline", []),
        "stats": detail_context.get("stats", {}),
        "current_balance": float(detail_context.get("client_balance") or 0),
    }

def filtered_sellable_items(request: Request):
    items = [dict(item) for item in build_sellable_items()]
    term = str(request.query_params.get("q", "") or "").strip().lower()
    kind_filter = str(request.query_params.get("kind", "") or "").strip().lower()
    if term:
        items = [item for item in items if term in str(item.get("label", "")).lower() or term in str(item.get("key", "")).lower()]
    if kind_filter in {"finished", "raw"}:
        items = [item for item in items if str(item.get("key", "")).startswith(f"{kind_filter}:")]
    return api_success(items, {"returned": len(items)})
