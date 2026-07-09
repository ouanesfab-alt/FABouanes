from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, case, literal_column, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import api_success
from app.modules.sales.repository import build_sellable_items
from app.core.models import Client, Supplier, RawMaterial, FinishedProduct, ProductionBatch, Purchase, Sale, RawSale, Payment

def json_response(payload: dict[str, Any]) -> JSONResponse:
    status_code = int(payload.pop("_status_code", 200))
    return JSONResponse(jsonable_encoder(payload), status_code=status_code)

async def _get_db_fallback(db: AsyncSession | None) -> AsyncSession:
    if db is not None:
        return db
    from app.core.async_db import get_async_session
    async for session in get_async_session():
        return session

async def client_payload(client_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        *Client.__table__.columns,
        literal_column("current_balance"),
        literal_column("total_sales"),
        literal_column("total_payments")
    ).select_from(table("clients_with_stats")).where(Client.id == client_id)
    res = await session.execute(stmt)
    row = res.first()
    return dict(row._mapping) if row else None

async def supplier_payload(supplier_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    supplier = await session.get(Supplier, supplier_id)
    return supplier.model_dump() if supplier else None

async def raw_material_payload(material_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        *RawMaterial.__table__.columns,
        case(
            (RawMaterial.stock_qty <= func.coalesce(func.nullif(RawMaterial.threshold_qty, 0), RawMaterial.alert_threshold), 1),
            else_=0
        ).label("is_low_stock"),
        literal_column("'raw'").label("item_type")
    ).where(RawMaterial.id == material_id)
    res = await session.execute(stmt)
    row = res.first()
    return dict(row._mapping) if row else None

async def finished_product_payload(product_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        *FinishedProduct.__table__.columns,
        literal_column("'finished'").label("item_type")
    ).where(FinishedProduct.id == product_id)
    res = await session.execute(stmt)
    row = res.first()
    return dict(row._mapping) if row else None

async def production_payload(batch_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        ProductionBatch,
        FinishedProduct.name.label("product_name"),
        FinishedProduct.default_unit.label("product_unit")
    ).join(FinishedProduct, FinishedProduct.id == ProductionBatch.finished_product_id).where(ProductionBatch.id == batch_id)
    res = await session.execute(stmt)
    row = res.first()
    if row:
        dct = row[0].model_dump()
        dct["product_name"] = row.product_name
        dct["product_unit"] = row.product_unit
        return dct
    return None

async def purchase_payload(purchase_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        Purchase,
        func.coalesce(Supplier.name, 'Sans fournisseur').label("supplier_name"),
        RawMaterial.name.label("material_name"),
        RawMaterial.unit.label("material_unit")
    ).join(RawMaterial, RawMaterial.id == Purchase.raw_material_id).outerjoin(Supplier, Supplier.id == Purchase.supplier_id).where(Purchase.id == purchase_id)
    res = await session.execute(stmt)
    row = res.first()
    if row:
        dct = row[0].model_dump()
        dct["supplier_name"] = row.supplier_name
        dct["material_name"] = row.material_name
        dct["material_unit"] = row.material_unit
        return dct
    return None

async def sale_payload(kind: str, row_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    if kind == "finished":
        stmt = select(
            Sale,
            func.coalesce(Client.name, 'Comptoir').label("client_name"),
            FinishedProduct.name.label("item_name"),
            literal_column("'Produit fini'").label("item_kind"),
            literal_column("'finished'").label("row_kind"),
            func.concat('finished:', Sale.finished_product_id).label("item_key")
        ).join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id).outerjoin(Client, Client.id == Sale.client_id).where(Sale.id == row_id)
        res = await session.execute(stmt)
        row = res.first()
        if row:
            dct = row[0].model_dump()
            dct.update({
                "client_name": row.client_name,
                "item_name": row.item_name,
                "item_kind": row.item_kind,
                "row_kind": row.row_kind,
                "item_key": row.item_key
            })
            return dct
    else:
        stmt = select(
            RawSale,
            func.coalesce(Client.name, 'Comptoir').label("client_name"),
            RawMaterial.name.label("item_name"),
            literal_column("'Matiere premiere'").label("item_kind"),
            literal_column("'raw'").label("row_kind"),
            func.concat('raw:', RawSale.raw_material_id).label("item_key")
        ).join(RawMaterial, RawMaterial.id == RawSale.raw_material_id).outerjoin(Client, Client.id == RawSale.client_id).where(RawSale.id == row_id)
        res = await session.execute(stmt)
        row = res.first()
        if row:
            dct = row[0].model_dump()
            dct.update({
                "client_name": row.client_name,
                "item_name": row.item_name,
                "item_kind": row.item_kind,
                "row_kind": row.row_kind,
                "item_key": row.item_key
            })
            return dct
    return None

async def purchase_document_payload(document_id: int, db: AsyncSession):
    from app.modules.purchases.service import PurchaseService
    context = await PurchaseService(db).get_purchase_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["purchase_document"]),
        "lines": [dict(line) for line in context["purchase_lines"]],
        "line_count": len(context["purchase_lines"]),
    }

async def sale_document_payload(document_id: int, db: AsyncSession):
    from app.modules.sales.service import SalesService
    context = await SalesService(db).get_sale_document_context(document_id)
    if not context:
        return None
    return {
        "document": dict(context["sale_document"]),
        "lines": [dict(line) for line in context["sale_lines"]],
        "line_count": len(context["sale_lines"]),
        "has_linked_payments": bool(context["has_linked_payments"]),
    }

async def payment_payload(payment_id: int, db: AsyncSession | None = None):
    session = await _get_db_fallback(db)
    stmt = select(
        Payment,
        Client.name.label("client_name"),
        case(
            (Payment.sale_kind == 'finished', func.concat('finished:', Payment.sale_id)),
            (Payment.sale_kind == 'raw', func.concat('raw:', Payment.raw_sale_id)),
            else_=''
        ).label("sale_link"),
        case(
            (Payment.sale_kind == 'finished', func.concat('Produit #', Payment.sale_id)),
            (Payment.sale_kind == 'raw', func.concat('Matiere #', Payment.raw_sale_id)),
            else_='-'
        ).label("sale_ref")
    ).join(Client, Client.id == Payment.client_id).where(Payment.id == payment_id)
    res = await session.execute(stmt)
    row = res.first()
    if row:
        dct = row[0].model_dump()
        dct.update({
            "client_name": row.client_name,
            "sale_link": row.sale_link,
            "sale_ref": row.sale_ref
        })
        return dct
    return None

async def client_history_payload(client_id: int, db: AsyncSession):
    from app.modules.clients.service import ClientService
    detail_context = await ClientService(db).get_client_detail_context(client_id)
    if not detail_context:
        return None
    return {
        "client": await client_payload(client_id, db),
        "history": detail_context.get("timeline", []),
        "stats": detail_context.get("stats", {}),
        "current_balance": float(detail_context.get("client_balance") or 0),
    }

async def filtered_sellable_items(request: Request):
    items = [dict(item) for item in await build_sellable_items.async_()]
    term = str(request.query_params.get("q", "") or "").strip().lower()
    kind_filter = str(request.query_params.get("kind", "") or "").strip().lower()
    if term:
        items = [item for item in items if term in str(item.get("label", "")).lower() or term in str(item.get("key", "")).lower()]
    if kind_filter in {"finished", "raw"}:
        items = [item for item in items if str(item.get("key", "")).startswith(f"{kind_filter}:")]
    return api_success(items, {"returned": len(items)})
