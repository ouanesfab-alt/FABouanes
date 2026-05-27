from __future__ import annotations

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client
from app.modules.clients.repository import ClientRepository
from app.core.async_db import AsyncSessionLocal

@pytest.mark.asyncio
async def test_async_database_and_repositories():
    """Verify that we can obtain an AsyncSession and run CRUD on SQLModel entities via ClientRepository."""
    async with AsyncSessionLocal() as session:
        repo = ClientRepository(session)
        
        # 1. Clear any existing test clients to start fresh
        clients, total = await repo.list_clients(search="RefactorTestClient")
        for c in clients:
            await repo.delete(c.id)
        
        # 2. Create a new SQLModel client entity
        client = Client(
            name="RefactorTestClient",
            phone="0777777777",
            address="Test Street 42",
            notes="Asynchronous ORM unit testing notes",
            opening_credit=100.0,
        )
        created = await repo.create(client)
        assert created.id is not None
        assert created.name == "RefactorTestClient"
        assert created.opening_credit == 100.0

        # 3. Retrieve the record by ID
        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.name == "RefactorTestClient"

        # 4. Search and verify pagination
        found_list, found_total = await repo.list_clients(search="RefactorTestClient")
        assert found_total >= 1
        assert found_list[0].id == created.id

        # 5. Case insensitive lookup
        exact = await repo.find_by_name("refactortestclient")
        assert exact is not None
        assert exact.id == created.id

        # 6. Clean up
        success = await repo.delete(created.id)
        assert success is True
        
        # Double check it is deleted
        deleted = await repo.get_by_id(created.id)
        assert deleted is None

