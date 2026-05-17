from __future__ import annotations
import asyncio


from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.datastructures import FormData

from app.api.deps import api_success
from app.core.db_access import query_db, query_db_async

from app.repositories.sale_repository import build_sellable_items
from app.services.client_service import get_client_detail_context
from app.services.purchase_service import get_purchase_document_context
from app.services.sale_service import get_sale_document_context


def json_response(payload: dict[str, Any]) -> JSONResponse:
    status_code = int(payload.pop("_status_code", 200))
    return JSONResponse(payload, status_code=status_code)


def payload_to_form_data(payload: dict[str, Any]) -> FormData:
    items: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, list):
            for item in value:
                items.append((key, item))
        else:
            items.append((key, value))
    return FormData(items)


def pagination_meta(request: Request) -> tuple[int, int, int]:
    page = max(int(request.query_params.get("page", "1") or "1"), 1)
    page_size = min(max(int(request.query_params.get("page_size", "50") or "50"), 1), 200)
    offset = (page - 1) * page_size
    return page, page_size, offset


def query_list(request: Request, query: str, params: tuple[Any, ...] = ()) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page, page_size, offset = pagination_meta(request)
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({query}) _q LIMIT ? OFFSET ?"
    rows = query_db(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(row) for row in rows], {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total,
    }

async def query_list_async(request: Request, query: str, params: tuple[Any, ...] = ()) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page, page_size, offset = pagination_meta(request)
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({query}) _q LIMIT ? OFFSET ?"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(row) for row in rows], {
        "page": page,
        "page_size": page_size,
        "returned": len(rows),
        "total": total,
    }



def like_value(request: Request) -> str:
    return f"%{request.query_params.get('q', '').strip()}%"


def append_text_search(request: Request, where: list[str], params: list[Any], *fields: str) -> None:
    if not request.query_params.get("q", "").strip():
        return
    clause = " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE LOWER(?)" for field in fields)
    where.append(f"({clause})")
    like = like_value(request)
    params.extend([like] * len(fields))


def append_date_range(request: Request, where: list[str], params: list[Any], field: str) -> None:
    date_from = str(request.query_params.get("date_from", "") or "").strip()
    date_to = str(request.query_params.get("date_to", "") or "").strip()
    if date_from:
        where.append(f"{field} >= ?")
        params.append(date_from)
    if date_to:
        where.append(f"{field} <= ?")
        params.append(date_to)


def client_balance_sql(alias: str = "c") -> str:
    return f"""
        {alias}.opening_credit
        + COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = {alias}.id AND s.sale_type = 'credit'), 0)
        + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = {alias}.id AND rs.sale_type = 'credit'), 0)
        - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = {alias}.id AND p.payment_type = 'versement'), 0)
        + COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = {alias}.id AND p.payment_type = 'avance'), 0)
    """


def client_total_sales_sql(alias: str = "c") -> str:
    return f"""
        COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = {alias}.id), 0)
        + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = {alias}.id), 0)
    """


def client_total_payments_sql(alias: str = "c") -> str:
    return f"COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = {alias}.id AND p.payment_type = 'versement'), 0)"


def client_payload(client_id: int):
    row = query_db(
        f"""
        SELECT c.*,
               {client_balance_sql("c")} AS current_balance,
               {client_balance_sql("c")} AS current_debt,
               {client_total_sales_sql("c")} AS total_sales,
               {client_total_payments_sql("c")} AS total_payments
        FROM clients c
        WHERE c.id = ?
        """,
        (client_id,),
        one=True,
    )
    return dict(row) if row else None


def supplier_payload(supplier_id: int):
    row = query_db("SELECT * FROM suppliers WHERE id = ?", (supplier_id,), one=True)
    return dict(row) if row else None


def raw_material_payload(material_id: int):
    row = query_db(
        """
        SELECT *,
               CASE WHEN stock_qty <= COALESCE(NULLIF(threshold_qty, 0), alert_threshold) THEN 1 ELSE 0 END AS is_low_stock,
               'raw' AS item_type
        FROM raw_materials
        WHERE id = ?
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
        WHERE id = ?
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
        WHERE pb.id = ?
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
        WHERE p.id = ?
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
            WHERE s.id = ?
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
            WHERE rs.id = ?
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
        WHERE p.id = ?
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


async def filtered_sellable_items(request: Request):
    items = [dict(item) for item in await asyncio.to_thread(build_sellable_items)]
    term = str(request.query_params.get("q", "") or "").strip().lower()
    kind_filter = str(request.query_params.get("kind", "") or "").strip().lower()
    if term:
        items = [item for item in items if term in str(item.get("label", "")).lower() or term in str(item.get("key", "")).lower()]
    if kind_filter in {"finished", "raw"}:
        items = [item for item in items if str(item.get("key", "")).startswith(f"{kind_filter}:")]
    return api_success(items, {"returned": len(items)})

