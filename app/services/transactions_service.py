from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat

from app.utils.pagination import (
    parse_pagination,
    MAX_PAGE_SIZE,
    pagination_context,
)
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.storage import backup_database


@async_compat
async def transactions_context(
    filter_type: str = "all",
    filter_name: str = "",
    filter_date: str = "",
    filter_operation: str = "",
    args=None,
    path: str = "/operations",
    db: AsyncSession | None = None,
) -> dict:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _transactions_context_impl(filter_type, filter_name, filter_date, filter_operation, args, path, session)
    return await _transactions_context_impl(filter_type, filter_name, filter_date, filter_operation, args, path, db)


async def _transactions_context_impl(
    filter_type: str,
    filter_name: str,
    filter_date: str,
    filter_operation: str,
    args,
    path: str,
    db: AsyncSession,
) -> dict:
    queries = []
    params: dict[str, Any] = {}
    
    name_filter = (filter_name or "").strip().lower()
    date_filter = (filter_date or "").strip()
    operation_filter = (filter_operation or "").strip().lower()
    
    # 1. Purchases query
    if filter_type in ("all", "purchase"):
        p_where = []
        if date_filter:
            p_where.append("p.purchase_date = :date_filter")
            params["date_filter"] = date_filter
        if name_filter:
            p_where.append("(lower(COALESCE(s.name, '')) LIKE :name_filter OR lower(COALESCE(r.name, '')) LIKE :name_filter OR lower(COALESCE(fp.name, '')) LIKE :name_filter)")
            params["name_filter"] = f"%{name_filter}%"
        if operation_filter:
            p_where.append("lower('Achat') LIKE :operation_filter")
            params["operation_filter"] = f"%{operation_filter}%"
            
        p_where_str = " AND ".join(p_where)
        p_where_clause = f"WHERE {p_where_str}" if p_where else ""
        
        p_query = f"""
            SELECT 'Achat' AS tx_type, 'purchase' AS tx_kind, p.id, p.purchase_date AS tx_date,
                   COALESCE(s.name, '-') AS partner_name, 
                   CASE 
                       WHEN p.finished_product_id IS NOT NULL THEN fp.name
                       ELSE r.name 
                   END AS designation,
                    CASE
                        WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) LIKE 'sac%%' THEN p.quantity / COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, r.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50')::numeric
                        WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                        ELSE p.quantity
                    END AS quantity,
                    COALESCE(p.unit, fp.default_unit, r.unit, 'kg') AS unit,
                    CASE
                        WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) LIKE 'sac%%' THEN p.unit_price * COALESCE(NULLIF(regexp_replace(COALESCE(p.unit, fp.default_unit, r.unit, 'kg'), '[^0-9.]', '', 'g'), ''), '50')::numeric
                        WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                        ELSE p.unit_price
                    END AS unit_price,
                   p.total, CAST(NULL AS numeric) AS paid, CAST(NULL AS numeric) AS due, p.document_id AS document_id, p.created_at AS tx_created_at
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            LEFT JOIN raw_materials r ON r.id = p.raw_material_id
            LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
            {p_where_clause}
        """
        queries.append(p_query)

    # 2. Sales query (finished + raw)
    if filter_type in ("all", "sale"):
        s_where = []
        if date_filter:
            s_where.append("x.sale_date = :date_filter")
            params["date_filter"] = date_filter
        if name_filter:
            s_where.append("(lower(COALESCE(x.client_name, '')) LIKE :name_filter OR lower(x.item_name) LIKE :name_filter)")
            params["name_filter"] = f"%{name_filter}%"
        if operation_filter:
            s_where.append("lower('Vente') LIKE :operation_filter")
            params["operation_filter"] = f"%{operation_filter}%"
            
        s_where_str = " AND ".join(s_where)
        s_where_clause = f"WHERE {s_where_str}" if s_where else ""
        
        s_query = f"""
            SELECT 'Vente' AS tx_type,
                   CASE WHEN x.row_kind='finished' THEN 'sale_finished' ELSE 'sale_raw' END AS tx_kind,
                   x.id, x.sale_date AS tx_date, COALESCE(x.client_name, '-') AS partner_name, x.item_name AS designation,
                   x.quantity, x.unit, x.unit_price, x.total, x.amount_paid AS paid, x.balance_due AS due, x.document_id AS document_id, x.created_at AS tx_created_at
            FROM (
                SELECT s.id, s.document_id, 'finished' AS row_kind, s.sale_date, c.name AS client_name, f.name AS item_name, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due, s.created_at
                FROM sales s LEFT JOIN clients c ON c.id = s.client_id JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT rs.id, rs.document_id, 'raw' AS row_kind, rs.sale_date, c.name AS client_name, r.name AS item_name, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due, rs.created_at
                FROM raw_sales rs LEFT JOIN clients c ON c.id = rs.client_id JOIN raw_materials r ON r.id = rs.raw_material_id
            ) x
            {s_where_clause}
        """
        queries.append(s_query)

    # 3. Payments query
    if filter_type in ("all", "payment"):
        pay_where = []
        if date_filter:
            pay_where.append("p.payment_date = :date_filter")
            params["date_filter"] = date_filter
        if name_filter:
            pay_where.append("(lower(COALESCE(c.name, '')) LIKE :name_filter OR lower(CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END) LIKE :name_filter)")
            params["name_filter"] = f"%{name_filter}%"
        if operation_filter:
            pay_where.append("lower(CASE WHEN p.payment_type='avance' THEN 'Avance' ELSE 'Versement' END) LIKE :operation_filter")
            params["operation_filter"] = f"%{operation_filter}%"
            
        pay_where_str = " AND ".join(pay_where)
        pay_where_clause = f"WHERE {pay_where_str}" if pay_where else ""
        
        pay_query = f"""
            SELECT CASE WHEN p.payment_type='avance' THEN 'Avance' ELSE 'Versement' END AS tx_type, 'payment' AS tx_kind, p.id, p.payment_date AS tx_date,
                   c.name AS partner_name,
                   CASE
                       WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Versement vente #' || CAST(p.sale_id AS VARCHAR)
                       WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Versement vente matiere #' || CAST(p.raw_sale_id AS VARCHAR)
                       ELSE CASE WHEN p.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END
                   END AS designation,
                   CAST(NULL AS numeric) AS quantity, CAST(NULL AS varchar) AS unit, CAST(NULL AS numeric) AS unit_price, p.amount AS total, p.amount AS paid, CAST(NULL AS numeric) AS due, CAST(NULL AS integer) AS document_id, p.created_at AS tx_created_at
            FROM payments p JOIN clients c ON c.id = p.client_id
            {pay_where_clause}
        """
        queries.append(pay_query)
        
    if not queries:
        union_query = "SELECT CAST(NULL AS varchar) AS tx_type LIMIT 0"
    else:
        union_query = " UNION ALL ".join(queries)
        
    full_query = f"""
        SELECT * FROM (
            {union_query}
        ) t
        ORDER BY tx_date DESC, tx_created_at DESC, id DESC
    """
    
    requested_size = int((args or {}).get("page_size", 0) or 0)
    page, page_size, offset = parse_pagination(args)
    if requested_size > MAX_PAGE_SIZE:
        page_size = requested_size
        
    count_res = await db.execute(text(f"SELECT COUNT(*) AS c FROM ({full_query}) paginated_query"), params)
    count_row = count_res.first()
    total = int(count_row.c if count_row else 0)
    
    limit_params = {**params, "limit": page_size, "offset": offset}
    rows_res = await db.execute(text(f"{full_query} LIMIT :limit OFFSET :offset"), limit_params)
    rows = rows_res.all()
    
    formatted_rows = []
    for row in rows:
        row_dict = dict(row._mapping)
        tx_created = row_dict.get("tx_created_at")
        if hasattr(tx_created, "strftime"):
            row_dict["tx_time"] = tx_created.strftime("%H:%M")
        elif isinstance(tx_created, str):
            row_dict["tx_time"] = tx_created.split()[1][:5] if " " in tx_created else ""
        else:
            row_dict["tx_time"] = ""
        formatted_rows.append(row_dict)
        
    pagination = pagination_context(path, args, total=total, page=page, page_size=page_size)
    
    return {
        "transactions": formatted_rows,
        "filter_type": filter_type,
        "filter_name": filter_name,
        "filter_date": filter_date,
        "filter_operation": filter_operation,
        "pagination": pagination,
    }


@async_compat
async def update_production_notes(
    batch_id: int,
    production_date: str,
    notes: str,
    db: AsyncSession | None = None,
) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _update_production_notes_impl(batch_id, production_date, notes, session)
            await session.commit()
            return
    await _update_production_notes_impl(batch_id, production_date, notes, db)


async def _update_production_notes_impl(
    batch_id: int,
    production_date: str,
    notes: str,
    db: AsyncSession,
) -> None:
    if not batch_id:
        raise ValueError("Identifiant manquant.")
        
    before_res = await db.execute(
        text("SELECT * FROM production_batches WHERE id = :batch_id"),
        {"batch_id": batch_id},
    )
    before_row = before_res.first()
    if not before_row:
        raise ValueError("Production introuvable.")
    before = dict(before_row._mapping)
    
    updates = {}
    if production_date:
        updates["production_date"] = production_date
    updates["notes"] = notes
    
    ALLOWED_KEYS = {"production_date", "notes"}
    for key in updates:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"Key {key} is not allowed for update")

    sets = ", ".join(f"{key}=:{key}" for key in updates)
    values = {**updates, "batch_id": batch_id}
    await db.execute(text(f"UPDATE production_batches SET {sets} WHERE id = :batch_id"), values)
    
    after_res = await db.execute(
        text("SELECT * FROM production_batches WHERE id = :batch_id"),
        {"batch_id": batch_id},
    )
    after = dict(after_res.first()._mapping)
    
    log_activity("edit_production_notes", "production", batch_id, f"date={production_date}")
    audit_event("edit_production_notes", "production", batch_id, before=before, after=after)
    backup_database("edit_production_notes")
