from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat
from app.core.models import Supplier
from app.utils.pagination import paginate_sequence
from app.core.perf_cache import async_cached_result
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.core.storage import backup_database


@async_compat
async def contacts_context(
    filter_type: str = "all",
    filter_name: str = "",
    args=None,
    path: str = "/contacts",
    db: AsyncSession | None = None,
) -> dict:
    normalized_type = (filter_type or "all").strip().lower() or "all"
    normalized_name = (filter_name or "").strip().lower()

    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _build_contacts_context(normalized_type, normalized_name, filter_name or "", session)
        return await _build_contacts_context(normalized_type, normalized_name, filter_name or "", db)

    base = await async_cached_result(
        ("contacts_context", normalized_type, normalized_name),
        load,
        ttl_seconds=6.0,
    )
    contacts, pagination = paginate_sequence(list(base["contacts"]), args or {}, path)
    return {
        **base,
        "contacts": contacts,
        "pagination": pagination,
    }


async def _build_contacts_context(filter_type: str, filter_name: str, raw_filter_name: str, db: AsyncSession) -> dict:
    res = await db.execute(
        text("""
        SELECT * FROM (
            SELECT 'Client' AS contact_type, c.id, c.name, c.phone, c.address, c.notes,
                   c.opening_credit
                   + COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id AND s.sale_type = 'credit'), 0)
                   + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id AND rs.sale_type = 'credit'), 0)
                   - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0)
                   + COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'avance'), 0) AS current_balance,
                   COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id), 0)
                   + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id), 0) AS total_amount,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'versement'), 0) AS total_paid,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type = 'avance'), 0) AS total_advance
            FROM clients c
            UNION ALL
            SELECT 'Fournisseur' AS contact_type, s.id, s.name, s.phone, s.address, s.notes,
                   0 AS current_balance,
                   COALESCE((SELECT SUM(total) FROM purchases p WHERE p.supplier_id = s.id), 0) AS total_amount,
                   0 AS total_paid,
                   0 AS total_advance
            FROM suppliers s
        ) x ORDER BY contact_type, name
        """)
    )
    rows = res.all()
    filtered_rows = []
    for row in rows:
        row_dict = dict(row._mapping)
        if filter_type == "client" and row_dict["contact_type"] != "Client":
            continue
        if filter_type == "supplier" and row_dict["contact_type"] != "Fournisseur":
            continue
        haystack = f"{row_dict['name']} {row_dict['phone'] or ''} {row_dict['address'] or ''}".lower()
        if filter_name and filter_name not in haystack:
            continue
        filtered_rows.append(row_dict)
    return {
        "contacts": filtered_rows,
        "filter_type": filter_type,
        "filter_name": raw_filter_name,
    }


@async_compat
async def create_supplier_from_form(form, db: AsyncSession | None = None) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _create_supplier_from_form_impl(form, session)
            await session.commit()
            return res
    return await _create_supplier_from_form_impl(form, db)


async def _create_supplier_from_form_impl(form, db: AsyncSession) -> int:
    name = str(form["name"]).strip()
    new_supplier = Supplier(
        name=name,
        phone=str(form.get("phone", "")).strip(),
        address=str(form.get("address", "")).strip(),
        notes=str(form.get("notes", "")).strip(),
    )
    db.add(new_supplier)
    await db.flush()

    supplier_id = new_supplier.id
    created = await _get_supplier_impl(supplier_id, db)
    log_activity("create_supplier", "supplier", supplier_id, name)
    audit_event("create_supplier", "supplier", supplier_id, after=created)
    backup_database("create_supplier")
    return supplier_id


@async_compat
async def get_supplier(supplier_id: int, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_supplier_impl(supplier_id, session)
    return await _get_supplier_impl(supplier_id, db)


async def _get_supplier_impl(supplier_id: int, db: AsyncSession):
    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supplier = res.scalars().first()
    return supplier.model_dump() if supplier else None


@async_compat
async def update_supplier_from_form(supplier_id: int, form, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _update_supplier_from_form_impl(supplier_id, form, session)
            await session.commit()
            return
    await _update_supplier_from_form_impl(supplier_id, form, db)


async def _update_supplier_from_form_impl(supplier_id: int, form, db: AsyncSession) -> None:
    before = await _get_supplier_impl(supplier_id, db)

    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supplier = res.scalars().first()
    if supplier:
        supplier.name = str(form["name"]).strip()
        supplier.phone = str(form.get("phone", "")).strip()
        supplier.address = str(form.get("address", "")).strip()
        supplier.notes = str(form.get("notes", "")).strip()
        db.add(supplier)

    updated = await _get_supplier_impl(supplier_id, db)
    log_activity("update_supplier", "supplier", supplier_id, str(form["name"]).strip())
    audit_event("update_supplier", "supplier", supplier_id, before=before, after=updated)
    backup_database("update_supplier")


@async_compat
async def delete_supplier_by_id(supplier_id: int, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _delete_supplier_by_id_impl(supplier_id, session)
            await session.commit()
            return
    await _delete_supplier_by_id_impl(supplier_id, db)


async def _delete_supplier_by_id_impl(supplier_id: int, db: AsyncSession) -> None:
    before = await _get_supplier_impl(supplier_id, db)

    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    supplier = res.scalars().first()
    if supplier:
        await db.delete(supplier)

    log_activity("delete_supplier", "supplier", supplier_id, "Suppression fournisseur")
    audit_event("delete_supplier", "supplier", supplier_id, before=before, after=None)
    backup_database("delete_supplier")


@async_compat
async def get_supplier_detail_context(supplier_id: int, args=None, path: str | None = None, db: AsyncSession | None = None) -> dict | None:
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                return await _build_supplier_detail_context(supplier_id, session)
        return await _build_supplier_detail_context(supplier_id, db)

    base = await async_cached_result(("supplier_detail_context", int(supplier_id)), load, ttl_seconds=6.0)
    if not base:
        return None
    purchases, pagination = paginate_sequence(list(base["purchases"]), args or {}, path or f"/contacts/suppliers/{supplier_id}")
    return {
        **base,
        "purchases": purchases,
        "pagination": pagination,
    }


async def _build_supplier_detail_context(supplier_id: int, db: AsyncSession) -> dict | None:
    supplier = await _get_supplier_impl(supplier_id, db)
    if not supplier:
        return None
    res = await db.execute(
        text("""
        SELECT p.id, p.document_id, p.purchase_date AS event_date,
               COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS designation,
               p.quantity, COALESCE(p.unit, r.unit, 'kg') AS unit, p.unit_price, p.total, p.notes
        FROM purchases p
        JOIN raw_materials r ON r.id = p.raw_material_id
        WHERE p.supplier_id = :supplier_id
        ORDER BY p.purchase_date DESC, p.id DESC
        """),
        {"supplier_id": supplier_id},
    )
    purchases_rows = [dict(row._mapping) for row in res.all()]
    total_amount = sum(float(item["total"]) for item in purchases_rows)
    return {
        "supplier": supplier,
        "purchases": purchases_rows,
        "purchase_count": len(purchases_rows),
        "total_amount": total_amount,
    }
