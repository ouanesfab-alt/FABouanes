from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, or_, func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client
from app.repositories.base_repository import AsyncRepository


class ClientRepository(AsyncRepository[Client]):
    """Asynchronous repository for the Client model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Client)

    async def get_by_id(self, client_id: int) -> Optional[Client]:
        """Fetch client by ID."""
        return await self.get(client_id)

    async def list_clients(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 50
    ) -> Tuple[List[Client], int]:
        """Fetch paginated clients with optional search filter."""
        offset = (page - 1) * page_size
        statement = select(Client)

        if search:
            search_filter = f"%{search}%"
            statement = statement.where(
                or_(
                    Client.name.ilike(search_filter),
                    Client.phone.ilike(search_filter),
                    Client.address.ilike(search_filter),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(statement.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginate results
        statement = statement.order_by(Client.name).offset(offset).limit(page_size)
        results = await self.session.execute(statement)
        clients = list(results.scalars().all())

        return clients, total

    async def find_by_name(self, name: str) -> Optional[Client]:
        """Fetch client by case-insensitive name."""
        statement = select(Client).where(func.lower(Client.name) == name.strip().lower())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def has_operations(self, client_id: int) -> bool:
        """Check if client has any sales or payments (prevents deletion)."""
        result = await self.session.execute(
            text(
                "SELECT 1 FROM sales WHERE client_id = :cid "
                "UNION SELECT 1 FROM raw_sales WHERE client_id = :cid "
                "UNION SELECT 1 FROM payments WHERE client_id = :cid "
                "LIMIT 1"
            ),
            {"cid": client_id},
        )
        return result.first() is not None

    async def get_timeline(self, client_id: int) -> List[Dict[str, Any]]:
        """Build full client timeline: sales + raw_sales + payments."""
        result = await self.session.execute(
            text("""
                SELECT row_id, document_id, sort_sequence, event_date,
                       designation, item_name, quantity, unit,
                       purchase_amount, payment_amount, event_type
                FROM (
                    SELECT s.id AS row_id, s.document_id AS document_id,
                           COALESCE(s.document_id, s.id) AS sort_sequence,
                           s.sale_date AS event_date,
                           NULL AS designation, f.name AS item_name,
                           s.quantity AS quantity, s.unit AS unit,
                           s.total AS purchase_amount, 0.0 AS payment_amount,
                           'sale_finished' AS event_type
                    FROM sales s
                    JOIN finished_products f ON f.id = s.finished_product_id
                    WHERE s.client_id = :cid
                    UNION ALL
                    SELECT rs.id AS row_id, rs.document_id AS document_id,
                           COALESCE(rs.document_id, rs.id) AS sort_sequence,
                           rs.sale_date AS event_date,
                           NULL AS designation,
                           COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                           rs.quantity AS quantity, rs.unit AS unit,
                           rs.total AS purchase_amount, 0.0 AS payment_amount,
                           'sale_raw' AS event_type
                    FROM raw_sales rs
                    JOIN raw_materials r ON r.id = rs.raw_material_id
                    WHERE rs.client_id = :cid
                    UNION ALL
                    SELECT p.id AS row_id, NULL AS document_id,
                           p.id AS sort_sequence, p.payment_date AS event_date,
                           CASE
                               WHEN p.sale_kind = 'raw' THEN 'Versement lié à la vente matière'
                               WHEN p.sale_kind = 'finished' THEN 'Versement lié à la vente produit'
                               ELSE COALESCE(NULLIF(p.notes,''),
                                    CASE WHEN p.payment_type='avance' THEN 'Avance client'
                                         ELSE 'Versement client' END)
                           END AS designation,
                           NULL AS item_name, NULL AS quantity, NULL AS unit,
                           CASE WHEN p.payment_type='avance' THEN p.amount ELSE 0 END AS purchase_amount,
                           CASE WHEN p.payment_type='versement' THEN p.amount ELSE 0 END AS payment_amount,
                           CASE WHEN p.payment_type='avance' THEN 'advance' ELSE 'payment' END AS event_type
                    FROM payments p
                    WHERE p.client_id = :cid
                ) events
                ORDER BY event_date,
                         CASE WHEN event_type IN ('sale_finished', 'sale_raw') THEN 0 ELSE 1 END,
                         row_id
            """),
            {"cid": client_id},
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_balance(self, client_id: int) -> Optional[float]:
        """Get client balance from materialized view."""
        result = await self.session.execute(
            text("SELECT balance FROM mv_client_balances WHERE client_id = :cid"),
            {"cid": client_id},
        )
        row = result.first()
        return float(row._mapping["balance"]) if row else None

    async def get_history_paginated(
        self, client_id: int, page: int = 1, page_size: int = 15
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated client history entries."""
        offset = (page - 1) * page_size

        # Count total
        count_result = await self.session.execute(
            text("SELECT COUNT(*) AS c FROM client_history WHERE client_id = :cid"),
            {"cid": client_id},
        )
        total = int(count_result.scalar() or 0)

        # Fetch page
        result = await self.session.execute(
            text("""
                SELECT * FROM client_history
                WHERE client_id = :cid
                ORDER BY operation_date ASC, id ASC
                LIMIT :lim OFFSET :off
            """),
            {"cid": client_id, "lim": page_size, "off": offset},
        )
        rows = [dict(row._mapping) for row in result.fetchall()]
        return rows, total

    async def get_history_stats(self, client_id: int) -> Dict[str, Any]:
        """Get aggregated stats from client_history."""
        result = await self.session.execute(
            text("""
                SELECT
                    COUNT(CASE WHEN source = 'import_excel' THEN 1 END) AS nb_excel,
                    COUNT(CASE WHEN source = 'app' THEN 1 END) AS nb_app,
                    COALESCE(SUM(montant_achat), 0) AS total_achats,
                    COALESCE(SUM(montant_verse), 0) AS total_versements
                FROM client_history
                WHERE client_id = :cid
            """),
            {"cid": client_id},
        )
        row = result.first()
        if row:
            m = row._mapping
            return {
                "nb_excel": int(m["nb_excel"] or 0),
                "nb_app": int(m["nb_app"] or 0),
                "total_achats": float(m["total_achats"] or 0),
                "total_versements": float(m["total_versements"] or 0),
            }
        return {"nb_excel": 0, "nb_app": 0, "total_achats": 0, "total_versements": 0}
