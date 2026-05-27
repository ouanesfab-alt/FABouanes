from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Set
from sqlmodel import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Sale, RawSale, SaleDocument, FinishedProduct
from app.repositories.base_repository import AsyncRepository


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
            result = await self.session.execute(
                text("""
                    SELECT s.*, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                           '' AS custom_item_name, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key
                    FROM sales s
                    LEFT JOIN clients c ON c.id = s.client_id
                    JOIN finished_products f ON f.id = s.finished_product_id
                    WHERE s.id = :row_id
                """),
                {"row_id": row_id}
            )
        else:
            result = await self.session.execute(
                text("""
                    SELECT rs.*, COALESCE(c.name, 'Comptoir') AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                           rs.custom_item_name, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key
                    FROM raw_sales rs
                    LEFT JOIN clients c ON c.id = rs.client_id
                    JOIN raw_materials r ON r.id = rs.raw_material_id
                    WHERE rs.id = :row_id
                """),
                {"row_id": row_id}
            )
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
        where: list[str] = []
        bind_params: dict[str, Any] = {}

        if search:
            where.append("(LOWER(COALESCE(client_name, '')) LIKE LOWER(:search) OR LOWER(COALESCE(item_name, '')) LIKE LOWER(:search) OR LOWER(COALESCE(notes, '')) LIKE LOWER(:search))")
            bind_params["search"] = f"%{search}%"

        if date_from:
            where.append("sale_date >= :date_from")
            bind_params["date_from"] = date_from
        if date_to:
            where.append("sale_date <= :date_to")
            bind_params["date_to"] = date_to

        if kind in {"finished", "raw"}:
            where.append("row_kind = :row_kind")
            bind_params["row_kind"] = kind

        if status == "paid":
            where.append("balance_due <= 0")
        elif status == "due":
            where.append("balance_due > 0")
        elif status in {"cash", "credit"}:
            where.append("sale_type = :sale_type")
            bind_params["sale_type"] = status

        base_query = """
            SELECT * FROM (
                SELECT s.id, s.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, f.name AS item_name,
                       s.document_id, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due, s.profit_amount, s.sale_type, s.notes,
                       s.created_at, 'Produit fini' AS item_kind, 'finished' AS row_kind
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT rs.id, rs.sale_date, COALESCE(c.name, 'Comptoir') AS client_name, r.name AS item_name,
                       rs.document_id, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due, rs.profit_amount, rs.sale_type, rs.notes,
                       rs.created_at, 'Matiere premiere' AS item_kind, 'raw' AS row_kind
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
            ) x
        """

        if where:
            base_query += " WHERE " + " AND ".join(where)

        offset = (page - 1) * page_size
        bind_params["limit"] = page_size
        bind_params["offset"] = offset

        wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY sale_date DESC, id DESC LIMIT :limit OFFSET :offset"
        result = await self.session.execute(text(wrapped), bind_params)
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
        products = res_prod.all()

        # Fetch raw materials
        res_raw = await self.session.execute(
            text("""
                SELECT id, name, unit, stock_qty, sale_price, avg_cost
                FROM raw_materials
                ORDER BY CASE WHEN upper(trim(name)) = 'AUTRE' THEN 1 ELSE 0 END, name
            """)
        )
        raw_materials = res_raw.all()

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
        result = await self.session.execute(
            text("""
                SELECT id, sale_id, raw_sale_id, allocation_meta
                FROM payments
                WHERE client_id = :client_id AND payment_type = 'versement'
            """),
            {"client_id": client_id}
        )
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
        result = await self.session.execute(
            text("""
                SELECT * FROM (
                    SELECT s.id AS row_id, s.document_id, s.sale_date, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due,
                           f.name AS item_name, 'finished' AS row_kind, 'finished:' || s.finished_product_id AS item_key,
                           'Produit fini' AS item_kind, '' AS custom_item_name
                    FROM sales s
                    JOIN finished_products f ON f.id = s.finished_product_id
                    WHERE s.document_id = :doc_id
                    UNION ALL
                    SELECT rs.id AS row_id, rs.document_id, rs.sale_date, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due,
                           r.name AS item_name, 'raw' AS row_kind, 'raw:' || rs.raw_material_id AS item_key,
                           'Matiere premiere' AS item_kind, rs.custom_item_name
                    FROM raw_sales rs
                    JOIN raw_materials r ON r.id = rs.raw_material_id
                    WHERE rs.document_id = :doc_id
                ) x ORDER BY row_id
            """),
            {"doc_id": doc_id}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def document_has_linked_payments(self, doc_id: int, client_id: int, refs: Set[Tuple[str, int]]) -> bool:
        result = await self.session.execute(
            text("""
                SELECT id, sale_id, raw_sale_id, allocation_meta
                FROM payments
                WHERE client_id = :client_id AND payment_type = 'versement'
            """),
            {"client_id": client_id}
        )
        payments = [dict(row._mapping) for row in result.fetchall()]
        for p in payments:
            if _payment_references_sale(p, refs):
                return True
        return False
