from __future__ import annotations

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Client
from app.core.event_bus import event_bus
from app.services.cache_service import cache_service
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


def test_cache_service_ttl():
    """Verify that the CacheService correctly saves, retrieves, and invalidates items."""
    cache_service.clear()
    
    # 1. Verify missed keys return None
    assert cache_service.get("nonexistent_test_key") is None

    # 2. Set key with high TTL
    cache_service.set("test_key", "value_123", ttl_seconds=600.0)
    assert cache_service.get("test_key") == "value_123"

    # 3. Invalidate key
    cache_service.invalidate("test_key")
    assert cache_service.get("test_key") is None

    # 4. Expire key check (simulated with very short TTL)
    cache_service.set("short_key", "temp_value", ttl_seconds=0.001)
    import time
    time.sleep(0.05)
    assert cache_service.get("short_key") is None


@pytest.mark.asyncio
async def test_event_bus_pub_sub():
    """Verify that the EventBus registers callbacks/coroutines, decouples events, and executes asynchronously."""
    received_sync = []
    received_async = []

    def sync_listener(data: str):
        received_sync.append(data)

    async def async_listener(data: str):
        received_async.append(data)

    # 1. Subscribe listeners to a test event
    event_bus.subscribe("test.event", sync_listener)
    event_bus.subscribe("test.event", async_listener)

    # 2. Publish event synchronously
    event_bus.publish_sync("test.event", data="sync_publish_payload")
    # Let event loop process the async listener scheduled task in background
    await asyncio.sleep(0.01)

    assert "sync_publish_payload" in received_sync
    assert "sync_publish_payload" in received_async

    # 3. Publish event asynchronously
    received_sync.clear()
    received_async.clear()
    await event_bus.publish_async("test.event", data="async_publish_payload")

    assert "async_publish_payload" in received_sync
    assert "async_publish_payload" in received_async

    # 4. Unsubscribe and verify no more publications are received
    event_bus.unsubscribe("test.event", sync_listener)
    event_bus.unsubscribe("test.event", async_listener)

    received_sync.clear()
    received_async.clear()
    event_bus.publish_sync("test.event", data="muted")
    await asyncio.sleep(0.01)

    assert len(received_sync) == 0
    assert len(received_async) == 0
