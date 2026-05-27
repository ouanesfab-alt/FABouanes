from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client
from app.core.events import DomainEvent, emit
from app.core.perf_cache import invalidate_client_cache
from app.modules.clients.repository import ClientRepository
from app.modules.clients.schemas_validation import ClientCreateSchema, ClientUpdateSchema


class ClientService:
    """Asynchronous business service layer for Clients."""

    def __init__(self, session: AsyncSession):
        self.repo = ClientRepository(session)

    async def _decrypt_client(self, client: Optional[Client]) -> Optional[Client]:
        if not client:
            return client
        from sqlalchemy import text
        import base64
        from app.core.security import decrypt_val
        res = await self.repo.session.execute(
            text("SELECT encryption_key FROM client_keys WHERE client_id = :client_id"),
            {"client_id": client.id}
        )
        row = res.mappings().first()
        key = base64.b64decode(row["encryption_key"]) if row and row["encryption_key"] else None
        
        client.phone = decrypt_val(client.phone, key)
        client.address = decrypt_val(client.address, key)
        return client

    async def _decrypt_clients(self, clients: List[Client]) -> List[Client]:
        if not clients:
            return clients
        client_ids = [c.id for c in clients if c.id]
        if not client_ids:
            return clients
            
        from sqlalchemy import text, bindparam
        import base64
        from app.core.security import decrypt_val
        
        res = await self.repo.session.execute(
            text("SELECT client_id, encryption_key FROM client_keys WHERE client_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": tuple(client_ids)}
        )
        keys_map = {}
        for row in res.mappings().all():
            keys_map[row["client_id"]] = base64.b64decode(row["encryption_key"])
            
        for client in clients:
            key = keys_map.get(client.id)
            client.phone = decrypt_val(client.phone, key)
            client.address = decrypt_val(client.address, key)
        return clients

    async def shred_client(self, client_id: int) -> bool:
        """Shreds a client's sensitive PII."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return False
            
        # Delete key
        from sqlalchemy import text
        await self.repo.session.execute(
            text("DELETE FROM client_keys WHERE client_id = :client_id"),
            {"client_id": client_id}
        )
        
        # Set phone & address to "[SHREDDED]"
        client.phone = "[SHREDDED]"
        client.address = "[SHREDDED]"
        
        await self.repo.update(client)
        invalidate_client_cache(client_id)
        
        emit(
            DomainEvent(
                "update",
                "client",
                client_id,
                f"Client #{client_id} anonymisé par crypto-shredding",
                after=client.model_dump(),
            )
        )
        return True

    async def get_client(self, client_id: int) -> Optional[Client]:
        """Fetch client by ID."""
        client = await self.repo.get_by_id(client_id)
        return await self._decrypt_client(client)

    async def list_clients(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 50
    ) -> Tuple[List[Client], int]:
        """List paginated clients."""
        clients, total = await self.repo.list_clients(search, page, page_size)
        return await self._decrypt_clients(clients), total

    async def create_client(self, schema: ClientCreateSchema) -> Client:
        """Create and persist a new client."""
        client = Client(
            name=schema.name,
            phone="",
            address="",
            notes=schema.notes,
            opening_credit=schema.opening_credit,
        )
        created = await self.repo.create(client)

        import os
        import base64
        key = os.urandom(32)
        b64_key = base64.b64encode(key).decode("utf-8")
        from sqlalchemy import text
        await self.repo.session.execute(
            text("INSERT INTO client_keys (client_id, encryption_key) VALUES (:client_id, :key)"),
            {"client_id": created.id, "key": b64_key}
        )
        await self.repo.session.commit()

        from app.core.security import encrypt_val
        created.phone = encrypt_val(schema.phone, key)
        created.address = encrypt_val(schema.address, key)
        
        updated = await self.repo.update(created)
        decrypted = await self._decrypt_client(updated)

        # Publish domain event for auditing/logging
        emit(
            DomainEvent(
                "create",
                "client",
                decrypted.id,
                f"Nouveau client créé: {decrypted.name}",
                after=decrypted.model_dump(),
            )
        )
        return decrypted

    async def update_client(
        self, client_id: int, schema: ClientUpdateSchema
    ) -> Optional[Client]:
        """Update properties of an existing client."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return None

        # Fetch key
        from sqlalchemy import text
        import base64
        res = await self.repo.session.execute(
            text("SELECT encryption_key FROM client_keys WHERE client_id = :client_id"),
            {"client_id": client.id}
        )
        row = res.mappings().first()
        key = base64.b64decode(row["encryption_key"]) if row and row["encryption_key"] else None
        if not key:
            import os
            key = os.urandom(32)
            b64_key = base64.b64encode(key).decode("utf-8")
            await self.repo.session.execute(
                text("INSERT INTO client_keys (client_id, encryption_key) VALUES (:client_id, :key)"),
                {"client_id": client.id, "key": b64_key}
            )
            await self.repo.session.commit()

        from app.core.security import decrypt_val, encrypt_val
        decrypted_before = Client(
            id=client.id,
            name=client.name,
            phone=decrypt_val(client.phone, key),
            address=decrypt_val(client.address, key),
            notes=client.notes,
            opening_credit=client.opening_credit,
            created_at=client.created_at,
            updated_at=client.updated_at
        )
        before_dump = decrypted_before.model_dump()

        client.name = schema.name
        client.phone = encrypt_val(schema.phone, key)
        client.address = encrypt_val(schema.address, key)
        client.notes = schema.notes
        client.opening_credit = schema.opening_credit

        updated = await self.repo.update(client)

        # Invalidate cache for this specific client
        invalidate_client_cache(client_id)

        decrypted_after = await self._decrypt_client(updated)

        # Publish domain event for auditing/logging
        emit(
            DomainEvent(
                "update",
                "client",
                decrypted_after.id,
                f"Client mis à jour: {decrypted_after.name}",
                before=before_dump,
                after=decrypted_after.model_dump(),
            )
        )
        return decrypted_after

    async def delete_client(self, client_id: int) -> bool:
        """Delete an existing client (only if no operations linked)."""
        client = await self.repo.get_by_id(client_id)
        if not client:
            return False

        before_dump = client.model_dump()
        success = await self.repo.delete(client_id)

        if success:
            invalidate_client_cache(client_id)
            emit(
                DomainEvent(
                    "delete",
                    "client",
                    client_id,
                    f"Suppression client #{client_id}",
                    before=before_dump,
                )
            )
        return success

    async def has_operations(self, client_id: int) -> bool:
        """Check if client has linked sales or payments."""
        return await self.repo.has_operations(client_id)

    async def get_client_detail_context(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Build full client detail context with timeline and stats (async)."""
        from app.core.perf_cache import async_cached_result

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


def _format_quantity(value) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0.00"
    return f"{number:.2f}".rstrip("0").rstrip(".")
