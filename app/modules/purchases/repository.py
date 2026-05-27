from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Purchase, PurchaseDocument
from app.repositories.base_repository import AsyncRepository

class PurchaseRepository(AsyncRepository[Purchase]):
    """Asynchronous repository for the Purchase model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Purchase)

    async def get_by_id(self, purchase_id: int) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(
            text("""
                SELECT p.*, s.name AS supplier_name,
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN fp.name
                           ELSE COALESCE(NULLIF(p.custom_item_name, ''), r.name)
                       END AS material_name,
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                           ELSE COALESCE(p.unit, r.unit, 'kg')
                       END AS display_unit,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                           ELSE p.quantity
                       END AS display_quantity,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                           ELSE p.unit_price
                       END AS display_unit_price
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                LEFT JOIN raw_materials r ON r.id = p.raw_material_id
                LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
                WHERE p.id = :purchase_id
            """),
            {"purchase_id": purchase_id}
        )
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_purchases_paginated(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where: list[str] = []
        bind_params: dict[str, Any] = {}

        if search:
            where.append("(LOWER(COALESCE(supplier_name, '')) LIKE LOWER(:search) OR LOWER(COALESCE(material_name, '')) LIKE LOWER(:search) OR LOWER(COALESCE(notes, '')) LIKE LOWER(:search))")
            bind_params["search"] = f"%{search}%"

        if date_from:
            where.append("purchase_date >= :date_from")
            bind_params["date_from"] = date_from
        if date_to:
            where.append("purchase_date <= :date_to")
            bind_params["date_to"] = date_to

        base_query = """
            SELECT * FROM (
                SELECT p.id, p.purchase_date, p.supplier_id, p.document_id, p.raw_material_id, p.finished_product_id,
                       p.quantity, p.unit, p.unit_price, p.total, p.notes, p.created_at, p.updated_at,
                       s.name AS supplier_name,
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN fp.name
                           ELSE COALESCE(NULLIF(p.custom_item_name, ''), r.name)
                       END AS material_name, 
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                           ELSE COALESCE(p.unit, r.unit, 'kg')
                       END AS material_unit,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                           ELSE p.quantity
                       END AS display_quantity,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                           ELSE p.unit_price
                       END AS display_unit_price
                FROM purchases p
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                LEFT JOIN raw_materials r ON r.id = p.raw_material_id
                LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
            ) x
        """

        if where:
            base_query += " WHERE " + " AND ".join(where)

        offset = (page - 1) * page_size
        bind_params["limit"] = page_size
        bind_params["offset"] = offset

        wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY purchase_date DESC, id DESC LIMIT :limit OFFSET :offset"
        result = await self.session.execute(text(wrapped), bind_params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total

    async def list_raw_material_choices(self) -> List[Dict[str, Any]]:
        # Fetch raw materials
        res_raw = await self.session.execute(
            text("""
                SELECT id, name, unit, stock_qty, avg_cost, sale_price
                FROM raw_materials
            """)
        )
        raws = res_raw.fetchall()

        # Fetch finished products
        res_finished = await self.session.execute(
            text("""
                SELECT id, name, default_unit AS unit, stock_qty, avg_cost, sale_price
                FROM finished_products
            """)
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
        result = await self.session.execute(
            text("""
                SELECT pd.*, COALESCE(s.name, 'Sans fournisseur') AS supplier_name
                FROM purchase_documents pd
                LEFT JOIN suppliers s ON s.id = pd.supplier_id
                WHERE pd.id = :doc_id
            """),
            {"doc_id": doc_id}
        )
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_lines(self, doc_id: int) -> List[Dict[str, Any]]:
        result = await self.session.execute(
            text("""
                SELECT p.id AS row_id, p.document_id, p.supplier_id, p.purchase_date, p.notes, p.raw_material_id, p.finished_product_id,
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN fp.name
                           ELSE COALESCE(NULLIF(p.custom_item_name, ''), r.name)
                       END AS material_name, p.custom_item_name,
                       CASE 
                           WHEN p.finished_product_id IS NOT NULL THEN COALESCE(p.unit, fp.default_unit, 'kg')
                           ELSE COALESCE(p.unit, r.unit, 'kg')
                       END AS display_unit,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                           ELSE p.quantity
                       END AS display_quantity,
                       CASE
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                           WHEN lower(COALESCE(p.unit, fp.default_unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                           ELSE p.unit_price
                       END AS display_unit_price,
                       p.total
                FROM purchases p
                LEFT JOIN raw_materials r ON r.id = p.raw_material_id
                LEFT JOIN finished_products fp ON fp.id = p.finished_product_id
                WHERE p.document_id = :doc_id
                ORDER BY p.id ASC
            """),
            {"doc_id": doc_id}
        )
        return [dict(row._mapping) for row in result.fetchall()]
