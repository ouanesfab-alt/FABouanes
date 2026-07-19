from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, func, case, cast, Numeric, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Purchase, PurchaseDocument, Supplier, RawMaterial, FinishedProduct
from app.core.base_repository import AsyncRepository

class PurchaseRepository(AsyncRepository[Purchase]):
    """Asynchronous repository for the Purchase model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Purchase)

    async def get_by_id(self, purchase_id: int) -> Optional[Dict[str, Any]]:
        unit_expr = func.coalesce(Purchase.unit, FinishedProduct.default_unit, RawMaterial.unit, 'kg')

        material_name_expr = case(
            (Purchase.finished_product_id.is_not(None), FinishedProduct.name),
            else_=func.coalesce(func.nullif(Purchase.custom_item_name, ''), RawMaterial.name)
        )

        display_unit_expr = case(
            (Purchase.finished_product_id.is_not(None), func.coalesce(Purchase.unit, FinishedProduct.default_unit, 'kg')),
            else_=func.coalesce(Purchase.unit, RawMaterial.unit, 'kg')
        )

        sac_capacity_num = cast(func.coalesce(func.nullif(func.regexp_replace(unit_expr, '[^0-9.]', '', 'g'), ''), '50'), Numeric)

        display_quantity_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.quantity / sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.quantity / 100.0),
            else_=Purchase.quantity
        )

        display_unit_price_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.unit_price * sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.unit_price * 100.0),
            else_=Purchase.unit_price
        )

        stmt = (
            select(
                *Purchase.__table__.columns,
                Supplier.name.label("supplier_name"),
                material_name_expr.label("material_name"),
                display_unit_expr.label("display_unit"),
                display_quantity_expr.label("display_quantity"),
                display_unit_price_expr.label("display_unit_price")
            )
            .select_from(Purchase)
            .join(Supplier, Supplier.id == Purchase.supplier_id, isouter=True)
            .join(RawMaterial, RawMaterial.id == Purchase.raw_material_id, isouter=True)
            .join(FinishedProduct, FinishedProduct.id == Purchase.finished_product_id, isouter=True)
            .where(Purchase.id == purchase_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_purchases_paginated(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        unit_expr = func.coalesce(Purchase.unit, FinishedProduct.default_unit, RawMaterial.unit, 'kg')

        material_name_expr = case(
            (Purchase.finished_product_id.is_not(None), FinishedProduct.name),
            else_=func.coalesce(func.nullif(Purchase.custom_item_name, ''), RawMaterial.name)
        )

        material_unit_expr = case(
            (Purchase.finished_product_id.is_not(None), func.coalesce(Purchase.unit, FinishedProduct.default_unit, 'kg')),
            else_=func.coalesce(Purchase.unit, RawMaterial.unit, 'kg')
        )

        sac_capacity_num = cast(func.coalesce(func.nullif(func.regexp_replace(unit_expr, '[^0-9.]', '', 'g'), ''), '50'), Numeric)

        display_quantity_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.quantity / sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.quantity / 100.0),
            else_=Purchase.quantity
        )

        display_unit_price_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.unit_price * sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.unit_price * 100.0),
            else_=Purchase.unit_price
        )

        subquery_cols = [
            Purchase.id,
            Purchase.purchase_date,
            Purchase.supplier_id,
            Purchase.document_id,
            Purchase.raw_material_id,
            Purchase.finished_product_id,
            Purchase.quantity,
            Purchase.unit,
            Purchase.unit_price,
            Purchase.total,
            Purchase.notes,
            Purchase.custom_item_name,
            Purchase.created_at,
            Purchase.updated_at,
            Supplier.name.label("supplier_name"),
            material_name_expr.label("material_name"),
            material_unit_expr.label("material_unit"),
            display_quantity_expr.label("display_quantity"),
            display_unit_price_expr.label("display_unit_price")
        ]

        subq = (
            select(*subquery_cols)
            .select_from(Purchase)
            .join(Supplier, Supplier.id == Purchase.supplier_id, isouter=True)
            .join(RawMaterial, RawMaterial.id == Purchase.raw_material_id, isouter=True)
            .join(FinishedProduct, FinishedProduct.id == Purchase.finished_product_id, isouter=True)
        ).subquery("x")

        stmt = select(subq)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    func.coalesce(subq.c.supplier_name, '').ilike(search_pattern),
                    func.coalesce(subq.c.material_name, '').ilike(search_pattern),
                    func.coalesce(subq.c.notes, '').ilike(search_pattern)
                )
            )

        if date_from:
            stmt = stmt.where(subq.c.purchase_date >= date_from)
        if date_to:
            stmt = stmt.where(subq.c.purchase_date <= date_to)

        # Add total count column using window function
        stmt = stmt.add_columns(func.count().over().label("_total_count"))

        # Order and paginate
        stmt = (
            stmt.order_by(subq.c.purchase_date.desc(), subq.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(stmt)
        rows = [dict(row._mapping) for row in result.fetchall()]
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total

    async def list_raw_material_choices(self) -> List[Dict[str, Any]]:
        # Fetch raw materials
        res_raw = await self.session.execute(
            select(
                RawMaterial.id,
                RawMaterial.name,
                RawMaterial.unit,
                RawMaterial.stock_qty,
                RawMaterial.avg_cost,
                RawMaterial.sale_price
            )
        )
        raws = res_raw.fetchall()

        # Fetch finished products
        res_finished = await self.session.execute(
            select(
                FinishedProduct.id,
                FinishedProduct.name,
                FinishedProduct.default_unit.label("unit"),
                FinishedProduct.stock_qty,
                FinishedProduct.avg_cost,
                FinishedProduct.sale_price
            )
        )
        finished = res_finished.fetchall()

        choices = []
        for r in raws:
            is_autre = str(r.name or "").strip().casefold() == "autre"
            choices.append({
                "id": f"raw:{r.id}",
                "name": str(r.name),
                "unit": str(r.unit),
                "stock_qty": float(r.stock_qty),
                "avg_cost": float(r.avg_cost),
                "sale_price": float(r.sale_price),
                "option_label": f"{r.name} - autre produit" if is_autre else str(r.name),
                "force_unit": "unite" if is_autre else "",
                "custom_name_required": "1" if is_autre else ""
            })
        for f in finished:
            choices.append({
                "id": f"finished:{f.id}",
                "name": str(f.name),
                "unit": str(f.unit),
                "stock_qty": float(f.stock_qty),
                "avg_cost": float(f.avg_cost),
                "sale_price": float(f.sale_price),
                "option_label": f"{f.name} (Produit fini)",
                "force_unit": "",
                "custom_name_required": ""
            })

        def sort_key(x):
            is_autre = x["name"].upper().strip() == "AUTRE"
            return (1 if is_autre else 0, x["option_label"].lower())

        choices.sort(key=sort_key)
        return choices


class PurchaseDocumentRepository(AsyncRepository[PurchaseDocument]):
    """Asynchronous repository for the PurchaseDocument model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PurchaseDocument)

    async def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        stmt = (
            select(
                *PurchaseDocument.__table__.columns,
                func.coalesce(Supplier.name, 'Sans fournisseur').label("supplier_name")
            )
            .select_from(PurchaseDocument)
            .join(Supplier, Supplier.id == PurchaseDocument.supplier_id, isouter=True)
            .where(PurchaseDocument.id == doc_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_lines(self, doc_id: int) -> List[Dict[str, Any]]:
        unit_expr = func.coalesce(Purchase.unit, FinishedProduct.default_unit, RawMaterial.unit, 'kg')

        material_name_expr = case(
            (Purchase.finished_product_id.is_not(None), FinishedProduct.name),
            else_=func.coalesce(func.nullif(Purchase.custom_item_name, ''), RawMaterial.name)
        )

        display_unit_expr = case(
            (Purchase.finished_product_id.is_not(None), func.coalesce(Purchase.unit, FinishedProduct.default_unit, 'kg')),
            else_=func.coalesce(Purchase.unit, RawMaterial.unit, 'kg')
        )

        sac_capacity_num = cast(func.coalesce(func.nullif(func.regexp_replace(unit_expr, '[^0-9.]', '', 'g'), ''), '50'), Numeric)

        display_quantity_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.quantity / sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.quantity / 100.0),
            else_=Purchase.quantity
        )

        display_unit_price_expr = case(
            (func.lower(unit_expr).like('sac%'), Purchase.unit_price * sac_capacity_num),
            (func.lower(unit_expr).in_(['qt', 'quintal']), Purchase.unit_price * 100.0),
            else_=Purchase.unit_price
        )

        stmt = (
            select(
                Purchase.id.label("row_id"),
                Purchase.document_id,
                Purchase.supplier_id,
                Purchase.purchase_date,
                Purchase.notes,
                Purchase.raw_material_id,
                Purchase.finished_product_id,
                material_name_expr.label("material_name"),
                Purchase.custom_item_name,
                display_unit_expr.label("display_unit"),
                display_quantity_expr.label("display_quantity"),
                display_unit_price_expr.label("display_unit_price"),
                Purchase.total
            )
            .select_from(Purchase)
            .join(RawMaterial, RawMaterial.id == Purchase.raw_material_id, isouter=True)
            .join(FinishedProduct, FinishedProduct.id == Purchase.finished_product_id, isouter=True)
            .where(Purchase.document_id == doc_id)
            .order_by(Purchase.id.asc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]
