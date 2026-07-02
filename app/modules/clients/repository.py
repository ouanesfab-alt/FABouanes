from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import select, or_, func, case, literal, union_all, literal_column, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client, Sale, RawSale, FinishedProduct, RawMaterial, Payment, ClientHistory
from app.core.base_repository import AsyncRepository


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
        stmt1 = select(literal(1)).where(Sale.client_id == client_id)
        stmt2 = select(literal(1)).where(RawSale.client_id == client_id)
        stmt3 = select(literal(1)).where(Payment.client_id == client_id)
        union_stmt = union_all(stmt1, stmt2, stmt3).limit(1)
        result = await self.session.execute(union_stmt)
        return result.first() is not None

    async def get_timeline(self, client_id: int) -> List[Dict[str, Any]]:
        """Build full client timeline: sales + raw_sales + payments."""
        stmt_finished = (
            select(
                Sale.id.label("row_id"),
                Sale.document_id.label("document_id"),
                func.coalesce(Sale.document_id, Sale.id).label("sort_sequence"),
                Sale.sale_date.label("event_date"),
                literal(None).label("designation"),
                FinishedProduct.name.label("item_name"),
                Sale.quantity.label("quantity"),
                Sale.unit.label("unit"),
                Sale.total.label("purchase_amount"),
                literal(0.0).label("payment_amount"),
                literal("sale_finished").label("event_type")
            )
            .select_from(Sale)
            .join(FinishedProduct, FinishedProduct.id == Sale.finished_product_id)
            .where(Sale.client_id == client_id)
        )

        stmt_raw = (
            select(
                RawSale.id.label("row_id"),
                RawSale.document_id.label("document_id"),
                func.coalesce(RawSale.document_id, RawSale.id).label("sort_sequence"),
                RawSale.sale_date.label("event_date"),
                literal(None).label("designation"),
                func.coalesce(func.nullif(RawSale.custom_item_name, ''), RawMaterial.name).label("item_name"),
                RawSale.quantity.label("quantity"),
                RawSale.unit.label("unit"),
                RawSale.total.label("purchase_amount"),
                literal(0.0).label("payment_amount"),
                literal("sale_raw").label("event_type")
            )
            .select_from(RawSale)
            .join(RawMaterial, RawMaterial.id == RawSale.raw_material_id)
            .where(RawSale.client_id == client_id)
        )

        p_designation_expr = case(
            (Payment.sale_kind == 'raw', 'Versement lié à la vente matière'),
            (Payment.sale_kind == 'finished', 'Versement lié à la vente produit'),
            else_=func.coalesce(
                func.nullif(Payment.notes, ''),
                case(
                    (Payment.payment_type == 'avance', 'Avance client'),
                    else_='Versement client'
                )
            )
        )

        stmt_payments = (
            select(
                Payment.id.label("row_id"),
                literal(None).label("document_id"),
                Payment.id.label("sort_sequence"),
                Payment.payment_date.label("event_date"),
                p_designation_expr.label("designation"),
                literal(None).label("item_name"),
                literal(None).label("quantity"),
                literal(None).label("unit"),
                case((Payment.payment_type == 'avance', Payment.amount), else_=0.0).label("purchase_amount"),
                case((Payment.payment_type == 'versement', Payment.amount), else_=0.0).label("payment_amount"),
                case((Payment.payment_type == 'avance', 'advance'), else_='payment').label("event_type")
            )
            .select_from(Payment)
            .where(Payment.client_id == client_id)
        )

        union_stmt = union_all(stmt_finished, stmt_raw, stmt_payments).subquery("events")

        stmt = (
            select(
                union_stmt.c.row_id,
                union_stmt.c.document_id,
                union_stmt.c.sort_sequence,
                union_stmt.c.event_date,
                union_stmt.c.designation,
                union_stmt.c.item_name,
                union_stmt.c.quantity,
                union_stmt.c.unit,
                union_stmt.c.purchase_amount,
                union_stmt.c.payment_amount,
                union_stmt.c.event_type
            )
            .order_by(
                union_stmt.c.event_date,
                case(
                    (union_stmt.c.event_type.in_(['sale_finished', 'sale_raw']), 0),
                    else_=1
                ),
                union_stmt.c.row_id
            )
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_balance(self, client_id: int) -> Optional[float]:
        """Get client balance from materialized view."""
        stmt = (
            select(literal_column("balance"))
            .select_from(text("mv_client_balances"))
            .where(literal_column("client_id") == client_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return float(row._mapping["balance"]) if row else None

    async def get_history_paginated(
        self, client_id: int, page: int = 1, page_size: int = 15
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated client history entries."""
        offset = (page - 1) * page_size

        # Count total
        count_stmt = select(func.count(ClientHistory.id)).where(ClientHistory.client_id == client_id)
        count_result = await self.session.execute(count_stmt)
        total = int(count_result.scalar() or 0)

        # Fetch page
        stmt = (
            select(*ClientHistory.__table__.columns)
            .where(ClientHistory.client_id == client_id)
            .order_by(ClientHistory.operation_date.asc(), ClientHistory.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = [dict(row._mapping) for row in result.fetchall()]
        return rows, total

    async def get_history_stats(self, client_id: int) -> Dict[str, Any]:
        """Get aggregated stats from client_history."""
        stmt = (
            select(
                func.count(case((ClientHistory.source == 'import_excel', 1))).label("nb_excel"),
                func.count(case((ClientHistory.source == 'app', 1))).label("nb_app"),
                func.coalesce(func.sum(ClientHistory.montant_achat), 0.0).label("total_achats"),
                func.coalesce(func.sum(ClientHistory.montant_verse), 0.0).label("total_versements")
            )
            .where(ClientHistory.client_id == client_id)
        )
        result = await self.session.execute(stmt)
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
