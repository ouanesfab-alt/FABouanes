from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, literal_column, func

from app.core.models import Client, ClientKey
from app.core.perf_cache import async_cached_result
from app.modules.clients.infrastructure.repository import ClientRepository

def _format_quantity(value) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0.00"
    return f"{number:.2f}".rstrip("0").rstrip(".")


class ClientQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Clients."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ClientRepository(session)

    async def _decrypt_client(self, client: Optional[Client]) -> Optional[Client]:
        if not client:
            return client
        import base64
        from app.core.security import decrypt_val
        stmt = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id == client.id)
        res = await self.session.execute(stmt)
        row = res.mappings().first()
        key = base64.b64decode(row["encryption_key"]) if row and row.get("encryption_key") else None

        client.phone = decrypt_val(client.phone, key)
        client.address = decrypt_val(client.address, key)
        return client

    async def _decrypt_clients(self, clients: List[Client]) -> List[Client]:
        if not clients:
            return clients
        client_ids = [c.id for c in clients if c.id]
        if not client_ids:
            return clients

        import base64
        from app.core.security import decrypt_val

        stmt = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id.in_(client_ids))
        res = await self.session.execute(stmt)
        keys_map = {}
        for row in res.all():
            keys_map[row[0]] = base64.b64decode(row[1])

        for client in clients:
            key = keys_map.get(client.id)
            client.phone = decrypt_val(client.phone, key)
            client.address = decrypt_val(client.address, key)
        return clients

    async def get_client(self, client_id: int) -> Optional[Client]:
        """Fetch client by ID."""
        client = await self.repo.get_by_id(client_id)
        return await self._decrypt_client(client)

    async def list_clients(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 25
    ) -> Tuple[List[Client], int]:
        """List paginated clients."""
        clients, total = await self.repo.list_clients(search, page, page_size)
        return await self._decrypt_clients(clients), total

    async def list_clients_with_stats(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 25
    ) -> Tuple[List[dict], int]:
        """Lists clients with calculated statistics and balance from the database view."""
        from sqlalchemy import text
        stmt = select(
            *Client.__table__.columns,
            literal_column("current_balance"),
            literal_column("total_sales"),
            literal_column("total_payments")
        ).select_from(text("clients_with_stats"))

        if search:
            stmt = stmt.where(literal_column("search_vector").op("@@")(func.plainto_tsquery('french', search)))

        stmt = stmt.add_columns(func.count().over().label("_total_count"))

        offset = (page - 1) * page_size
        stmt = (
            stmt.order_by(literal_column("name"))
            .offset(offset)
            .limit(page_size)
        )

        res = await self.session.execute(stmt)
        rows = [dict(row._mapping) for row in res.fetchall()]

        if rows:
            client_ids = [c["id"] for c in rows if c.get("id")]
            if client_ids:
                import base64
                from app.core.security import decrypt_val

                stmt_keys = select(ClientKey.client_id, ClientKey.encryption_key).where(ClientKey.client_id.in_(client_ids))
                res_keys = await self.session.execute(stmt_keys)
                keys_map = {}
                for row in res_keys.all():
                    keys_map[row[0]] = base64.b64decode(row[1])

                for client in rows:
                    key = keys_map.get(client["id"])
                    client["phone"] = decrypt_val(client["phone"], key)
                    client["address"] = decrypt_val(client["address"], key)

        total = int(rows[0]["_total_count"]) if rows else 0
        return rows, total

    async def has_operations(self, client_id: int) -> bool:
        """Check if client has linked sales or payments."""
        return await self.repo.has_operations(client_id)

    async def get_client_detail_context(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Build full client detail context with timeline and stats (async)."""

        async def _load():
            client = await self.get_client(client_id)
            if not client:
                return None

            events = await self.repo.get_timeline(client_id)

            timeline = []
            created_at_str = (
                client.created_at.isoformat()
                if hasattr(client.created_at, "isoformat")
                else str(client.created_at or "")
            )

            if float(client.opening_credit) > 0:
                timeline.append(
                    {
                        "row_id": None,
                        "document_id": None,
                        "sort_sequence": 0,
                        "event_date": created_at_str[:10],
                        "designation": "Credit initial (reprise Excel)",
                        "purchase_amount": float(client.opening_credit),
                        "payment_amount": 0.0,
                        "event_type": "opening",
                    }
                )

            for row in events:
                item = dict(row)
                dt_val = item.get("event_date")
                if hasattr(dt_val, "strftime"):
                    item["event_date"] = dt_val.strftime("%Y-%m-%d")
                elif hasattr(dt_val, "isoformat"):
                    item["event_date"] = dt_val.isoformat()[:10]
                else:
                    item["event_date"] = str(dt_val or "")[:10]

                if item["event_type"] in ("sale_finished", "sale_raw"):
                    suffix = (
                        " (matière première)" if item["event_type"] == "sale_raw" else ""
                    )
                    qty = _format_quantity(item["quantity"])
                    unit = item["unit"] or ""
                    item["designation"] = (
                        f"{item['item_name']}{suffix} - {qty} {unit}".strip()
                    )
                timeline.append(item)

            timeline.sort(
                key=lambda item: (
                    item["event_date"],
                    0 if item["event_type"] in ("opening", "sale_finished", "sale_raw") else 1,
                    int(item.get("sort_sequence") or 0),
                )
            )

            running = 0.0
            for item in timeline:
                running += float(item.get("purchase_amount", 0) or 0)
                running -= float(item.get("payment_amount", 0) or 0)
                item["running_balance"] = running

            total_sales = sum(
                float(item["purchase_amount"])
                for item in timeline
                if item["event_type"] in ("sale_finished", "sale_raw")
            )
            total_advance = sum(
                float(item["purchase_amount"])
                for item in timeline
                if item["event_type"] == "advance"
            )
            total_paid = sum(
                float(item["payment_amount"])
                for item in timeline
                if item["event_type"] == "payment"
            )

            stats = {
                "opening_credit": float(client.opening_credit),
                "total_sales": total_sales,
                "running_balance": running,
                "credit_sales_total": float(client.opening_credit) + total_sales,
                "total_paid": total_paid,
                "total_advance": total_advance,
                "current_balance": running,
            }

            # Convert client to dict for template compatibility
            client_dict = {
                "id": client.id,
                "name": client.name,
                "phone": client.phone,
                "address": client.address,
                "notes": client.notes,
                "opening_credit": client.opening_credit,
                "created_at": client.created_at,
                "updated_at": client.updated_at,
            }

            return {
                "client": client_dict,
                "timeline": timeline,
                "stats": stats,
                "client_balance": running,
            }

        return await async_cached_result(("client_detail", int(client_id)), _load, ttl_seconds=30.0)

    async def get_history_page_context(
        self, client_id: int, page: int = 1, page_size: int = 15
    ) -> Optional[Dict[str, Any]]:
        """Build paginated history context for client history page."""
        client = await self.get_client(client_id)
        if not client:
            return None

        rows, total = await self.repo.get_history_paginated(client_id, page, page_size)
        total_pages = math.ceil(total / page_size) if page_size > 0 else 1
        stats = await self.repo.get_history_stats(client_id)

        balance = await self.repo.get_balance(client_id)
        client_balance = balance if balance is not None else float(client.opening_credit)

        client_dict = {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "address": client.address,
            "notes": client.notes,
            "opening_credit": client.opening_credit,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        }

        return {
            "client": client_dict,
            "client_balance": client_balance,
            "history": rows,
            "stats": stats,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        }
