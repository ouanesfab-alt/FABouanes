from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Set
from sqlmodel import select, func, case, literal, union_all, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Sale, RawSale, SaleDocument, FinishedProduct, Client, RawMaterial, Payment
from app.core.base_repository import AsyncRepository
from app.core.helpers import db_task_compat
from app.core.async_db import get_async_sessionmaker


def _payment_references_sale(payment_row: Dict[str, Any], sale_refs: Set[Tuple[str, int]]) -> bool:
    if payment_row.get("sale_id") and ("finished", int(payment_row["sale_id"])) in sale_refs:
        return True
    if payment_row.get("raw_sale_id") and ("raw", int(payment_row["raw_sale_id"])) in sale_refs:
        return True
    meta_raw = payment_row.get("allocation_meta")
    if not meta_raw:
        return False
    try:
        allocations = json.loads(meta_raw)
    except Exception:
        return False
    for allocation in allocations or []:
        try:
            ref = (str(allocation.get("kind") or ""), int(allocation.get("id") or 0))
        except Exception:
            continue
        if ref in sale_refs:
            return True
    return False


class SaleRepository(AsyncRepository[Sale]):
    """Asynchronous repository for the Sale model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Sale)

    async def get_by_id(self, sale_id: int) -> Optional[Sale]:
        return await self.get(sale_id)

    async def get_sale_detail(self, kind: str, row_id: int) -> Optional[Dict[str, Any]]:
        if kind == "finished":
            stmt = (
                select(
                    *Sale.__table__.columns,
                    func.coalesce(Client.name, 'Comptoir').label("client_name"),
                    FinishedProduct.name.label("item_name"),
                    literal("").label("custom_item_name"),
                    literal("finished").label("row_kind"),
                    func.concat("finished:", Sale.finished_product_id).label("item_key")
                )
                .select_from(Sale)
                .join(Client, Client.id == Sale.client_id, isouter=True)
                .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
                .where(Sale.id == row_id)
            )
        else:
            stmt = (
                select(
                    *RawSale.__table__.columns,
                    func.coalesce(Client.name, 'Comptoir').label("client_name"),
                    func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                    RawSale.custom_item_name,
                    literal("raw").label("row_kind"),
                    func.concat("raw:", RawSale.raw_material_id).label("item_key")
                )
                .select_from(RawSale)
                .join(Client, Client.id == RawSale.client_id, isouter=True)
                .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
                .where(RawSale.id == row_id)
            )
        result = await self.session.execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_sales_paginated(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch unified sales (finished + raw) paginated with count."""
        stmt_finished = (
            select(
                Sale.id,
                Sale.sale_date,
                func.coalesce(Client.name, 'Comptoir').label("client_name"),
                FinishedProduct.name.label("item_name"),
                Sale.document_id,
                Sale.quantity,
                Sale.unit,
                Sale.unit_price,
                Sale.total,
                Sale.amount_paid,
                Sale.balance_due,
                Sale.profit_amount,
                Sale.sale_type,
                Sale.notes,
                Sale.created_at,
                literal("Produit fini").label("item_kind"),
                literal("finished").label("row_kind")
            )
            .select_from(Sale)
            .join(Client, Client.id == Sale.client_id, isouter=True)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
        )
        
        stmt_raw = (
            select(
                RawSale.id,
                RawSale.sale_date,
                func.coalesce(Client.name, 'Comptoir').label("client_name"),
                RawMaterial.name.label("item_name"),
                RawSale.document_id,
                RawSale.quantity,
                RawSale.unit,
                RawSale.unit_price,
                RawSale.total,
                RawSale.amount_paid,
                RawSale.balance_due,
                RawSale.profit_amount,
                RawSale.sale_type,
                RawSale.notes,
                RawSale.created_at,
                literal("Matiere premiere").label("item_kind"),
                literal("raw").label("row_kind")
            )
            .select_from(RawSale)
            .join(Client, Client.id == RawSale.client_id, isouter=True)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
        )
        
        union_stmt = union_all(stmt_finished, stmt_raw).subquery("x")
        stmt = select(union_stmt)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    func.coalesce(union_stmt.c.client_name, '').ilike(search_pattern),
                    func.coalesce(union_stmt.c.item_name, '').ilike(search_pattern),
                    func.coalesce(union_stmt.c.notes, '').ilike(search_pattern)
                )
            )

        if date_from:
            stmt = stmt.where(union_stmt.c.sale_date >= date_from)
        if date_to:
            stmt = stmt.where(union_stmt.c.sale_date <= date_to)

        if kind in {"finished", "raw"}:
            stmt = stmt.where(union_stmt.c.row_kind == kind)

        if status == "paid":
            stmt = stmt.where(union_stmt.c.balance_due <= 0)
        elif status == "due":
            stmt = stmt.where(union_stmt.c.balance_due > 0)
        elif status in {"cash", "credit"}:
            stmt = stmt.where(union_stmt.c.sale_type == status)

        # Add total count column using window function
        stmt = stmt.add_columns(func.count().over().label("_total_count"))

        # Order and paginate
        stmt = (
            stmt.order_by(union_stmt.c.sale_date.desc(), union_stmt.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(stmt)
        rows = [dict(row._mapping) for row in result.fetchall()]
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total

    async def list_sellable_items(self) -> List[Dict[str, Any]]:
        # Fetch finished products
        res_prod = await self.session.execute(
            select(
                FinishedProduct.id,
                FinishedProduct.name,
                FinishedProduct.default_unit,
                FinishedProduct.stock_qty,
                FinishedProduct.sale_price,
                FinishedProduct.avg_cost
            ).order_by(FinishedProduct.name)
        )
        products = res_prod.fetchall()

        # Fetch raw materials
        res_raw = await self.session.execute(
            select(
                RawMaterial.id,
                RawMaterial.name,
                RawMaterial.unit,
                RawMaterial.stock_qty,
                RawMaterial.sale_price,
                RawMaterial.avg_cost
            ).order_by(
                case(
                    (func.upper(func.trim(RawMaterial.name)) == 'AUTRE', 1),
                    else_=0
                ),
                RawMaterial.name
            )
        )
        raw_materials = res_raw.fetchall()

        items = []
        for p in products:
            items.append({
                "key": f"finished:{p.id}",
                "label": f"{p.name} - produit final",
                "unit": p.default_unit,
                "stock_qty": float(p.stock_qty),
                "sale_price": float(p.sale_price),
                "avg_cost": float(p.avg_cost),
                "force_unit": "",
                "custom_name_required": "",
            })

        for rm in raw_materials:
            is_other = str(rm.name or "").strip().casefold() == "autre"
            items.append({
                "key": f"raw:{rm.id}",
                "label": f"{rm.name} - {'autre produit' if is_other else 'matière première'}",
                "unit": rm.unit,
                "stock_qty": float(rm.stock_qty),
                "sale_price": float(rm.sale_price),
                "avg_cost": float(rm.avg_cost),
                "force_unit": "unite" if is_other else "",
                "custom_name_required": "1" if is_other else "",
            })
        return items

    async def line_has_linked_payments(self, kind: str, row_id: int, client_id: int) -> bool:
        stmt = (
            select(
                Payment.id,
                Payment.sale_id,
                Payment.raw_sale_id,
                Payment.allocation_meta
            )
            .where(Payment.client_id == client_id)
            .where(Payment.payment_type == 'versement')
        )
        result = await self.session.execute(stmt)
        payments = [dict(row._mapping) for row in result.fetchall()]
        refs = {(kind, row_id)}
        for p in payments:
            if _payment_references_sale(p, refs):
                return True
        return False


class RawSaleRepository(AsyncRepository[RawSale]):
    """Asynchronous repository for the RawSale model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RawSale)


class SaleDocumentRepository(AsyncRepository[SaleDocument]):
    """Asynchronous repository for the SaleDocument model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SaleDocument)

    async def get_by_id(self, doc_id: int) -> Optional[SaleDocument]:
        return await self.get(doc_id)

    async def list_lines(self, doc_id: int) -> List[Dict[str, Any]]:
        stmt_finished = (
            select(
                Sale.id.label("row_id"),
                Sale.document_id,
                Sale.sale_date,
                Sale.quantity,
                Sale.unit,
                Sale.unit_price,
                Sale.total,
                Sale.amount_paid,
                Sale.balance_due,
                FinishedProduct.name.label("item_name"),
                literal("finished").label("row_kind"),
                func.concat("finished:", Sale.finished_product_id).label("item_key"),
                literal("Produit fini").label("item_kind"),
                literal("").label("custom_item_name")
            )
            .select_from(Sale)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
            .where(Sale.document_id == doc_id)
        )
        
        stmt_raw = (
            select(
                RawSale.id.label("row_id"),
                RawSale.document_id,
                RawSale.sale_date,
                RawSale.quantity,
                RawSale.unit,
                RawSale.unit_price,
                RawSale.total,
                RawSale.amount_paid,
                RawSale.balance_due,
                RawMaterial.name.label("item_name"),
                literal("raw").label("row_kind"),
                func.concat("raw:", RawSale.raw_material_id).label("item_key"),
                literal("Matiere premiere").label("item_kind"),
                RawSale.custom_item_name
            )
            .select_from(RawSale)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .where(RawSale.document_id == doc_id)
        )
        
        union_stmt = union_all(stmt_finished, stmt_raw).subquery("x")
        
        stmt = (
            select(union_stmt)
            .order_by(union_stmt.c.row_id.asc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]

    async def document_has_linked_payments(self, doc_id: int, client_id: int, refs: Set[Tuple[str, int]]) -> bool:
        stmt = (
            select(
                Payment.id,
                Payment.sale_id,
                Payment.raw_sale_id,
                Payment.allocation_meta
            )
            .where(Payment.client_id == client_id)
            .where(Payment.payment_type == 'versement')
        )
        result = await self.session.execute(stmt)
        payments = [dict(row._mapping) for row in result.fetchall()]
        for p in payments:
            if _payment_references_sale(p, refs):
                return True
        return False


# --- Legacy compatibility wrappers ---

def invalidate_sellable_items_cache() -> None:
    from app.core.perf_cache import invalidate_cache_domain
    invalidate_cache_domain("sales_sellable_items")
    from app.core.perf_cache import invalidate_cache_domains
    invalidate_cache_domains("dashboard", "sales", "client")


@db_task_compat
async def build_sellable_items(db: AsyncSession | None = None):
    from app.core.perf_cache import TTL_SEMI_STABLE
    
    async def load():
        if db is None:
            async with get_async_sessionmaker()() as session:
                repo = SaleRepository(session)
                return await repo.list_sellable_items()
        repo = SaleRepository(db)
        return await repo.list_sellable_items()

    from app.core.perf_cache import async_cached_result
    return await async_cached_result(("sales_sellable_items",), load, ttl_seconds=TTL_SEMI_STABLE)

