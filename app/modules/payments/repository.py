from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Payment
from app.repositories.base_repository import AsyncRepository

class PaymentRepository(AsyncRepository[Payment]):
    """Asynchronous repository for the Payment model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)

    async def get_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(
            text("""
                SELECT p.*, c.name AS client_name,
                       CASE
                           WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                           WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matière #' || p.raw_sale_id
                           ELSE '-'
                       END AS sale_ref
                FROM payments p
                JOIN clients c ON c.id = p.client_id
                WHERE p.id = :payment_id
            """),
            {"payment_id": payment_id}
        )
        row = result.first()
        return dict(row._mapping) if row else None

    async def list_payments_paginated(
        self,
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        where: list[str] = []
        bind_params: dict[str, Any] = {}

        if search:
            where.append("(LOWER(c.name) LIKE LOWER(:search) OR LOWER(COALESCE(p.notes, '')) LIKE LOWER(:search))")
            bind_params["search"] = f"%{search}%"

        if date_from:
            where.append("p.payment_date >= :date_from")
            bind_params["date_from"] = date_from
        if date_to:
            where.append("p.payment_date <= :date_to")
            bind_params["date_to"] = date_to

        if kind in {"versement", "avance"}:
            where.append("p.payment_type = :kind")
            bind_params["kind"] = kind

        base_query = """
            SELECT p.*, c.name AS client_name,
                   CASE
                       WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                       WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matière #' || p.raw_sale_id
                       ELSE '-'
                   END AS sale_ref
            FROM payments p
            JOIN clients c ON c.id = p.client_id
        """

        if where:
            base_query += " WHERE " + " AND ".join(where)

        offset = (page - 1) * page_size
        bind_params["limit"] = page_size
        bind_params["offset"] = offset

        wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY payment_date DESC, id DESC LIMIT :limit OFFSET :offset"
        result = await self.session.execute(text(wrapped), bind_params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total
