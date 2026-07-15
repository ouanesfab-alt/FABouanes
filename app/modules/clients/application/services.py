from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client
from app.modules.clients.api.schemas import ClientCreateSchema, ClientUpdateSchema
from app.modules.clients.application.queries import ClientQueries
from app.modules.clients.application.commands import ClientCommands


class ClientService:
    """Asynchronous business service layer for the Clients module, orchestrating Command-Query Separation (CQRS)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = ClientQueries(session)
        self.commands = ClientCommands(session)

    # ── [QUERIES] ──

    async def get_client(self, client_id: int) -> Optional[Client]:
        return await self.queries.get_client(client_id)

    async def list_clients(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 25
    ) -> Tuple[List[Client], int]:
        return await self.queries.list_clients(search, page, page_size)

    async def list_clients_with_stats(
        self, search: Optional[str] = None, page: int = 1, page_size: int = 25
    ) -> Tuple[List[dict], int]:
        return await self.queries.list_clients_with_stats(search, page, page_size)

    async def has_operations(self, client_id: int) -> bool:
        return await self.queries.has_operations(client_id)

    async def get_client_detail_context(self, client_id: int) -> Optional[Dict[str, Any]]:
        return await self.queries.get_client_detail_context(client_id)

    async def get_history_page_context(
        self, client_id: int, page: int = 1, page_size: int = 15
    ) -> Optional[Dict[str, Any]]:
        return await self.queries.get_history_page_context(client_id, page, page_size)

    # ── [COMMANDS] ──

    async def shred_client(self, client_id: int) -> bool:
        return await self.commands.shred_client(client_id)

    async def create_client(self, schema: ClientCreateSchema) -> Client:
        return await self.commands.create_client(schema)

    async def update_client(
        self, client_id: int, schema: ClientUpdateSchema
    ) -> Optional[Client]:
        return await self.commands.update_client(client_id, schema)

    async def delete_client(self, client_id: int) -> bool:
        return await self.commands.delete_client(client_id)

    async def preview_clients_from_files(self, files):
        return await self.commands.preview_clients_from_files(files)

    async def import_clients_from_preview(self, token: str):
        return await self.commands.import_clients_from_preview(token)

    async def import_clients_from_files(self, files):
        return await self.commands.import_clients_from_files(files)

    async def import_client_history_from_excel(
        self,
        file_path: str,
        client_id: int | None = None,
        force_reimport: bool = True
    ) -> dict:
        return await self.commands.import_client_history_from_excel(
            file_path=file_path,
            client_id=client_id,
            force_reimport=force_reimport
        )
