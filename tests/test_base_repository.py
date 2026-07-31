"""Tests unitaires pour app/core/base_repository.py (Phase 3.2)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.base_repository import AsyncRepository
from app.core.models import Client


@pytest.mark.asyncio
async def test_async_repository_crud():
    mock_session = AsyncMock()

    client_sample = Client(id=1, name="Client Test", phone="0550000000")

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [client_sample]
    mock_scalars.first.return_value = client_sample

    mock_res = MagicMock()
    mock_res.scalars.return_value = mock_scalars
    mock_res.scalar.return_value = 1

    mock_session.get.return_value = client_sample
    mock_session.execute = AsyncMock(return_value=mock_res)

    repo = AsyncRepository(mock_session, Client)

    # Get
    c = await repo.get(1)
    assert c is not None
    assert c.name == "Client Test"

    # List
    items = await repo.list(offset=0, limit=10)
    assert len(items) == 1

    # Create
    created = await repo.create(client_sample)
    assert created.id == 1
    mock_session.commit.assert_called()

    # Update
    updated = await repo.update(client_sample)
    assert updated.id == 1

    with pytest.raises(ValueError):
        await repo.update(None)

    # Count
    cnt = await repo.count()
    assert cnt == 1

    # Find by
    fb = await repo.find_by(name="Client Test")
    assert len(fb) == 1

    # Find one by
    fo = await repo.find_one_by(name="Client Test")
    assert fo is not None

    # Exists
    ex = await repo.exists(name="Client Test")
    assert ex is True

    # Create many
    cm = await repo.create_many([client_sample])
    assert len(cm) == 1

    # Delete
    deleted = await repo.delete(1)
    assert deleted is True

    # Delete non-existent
    mock_session.get.return_value = None
    deleted_false = await repo.delete(999)
    assert deleted_false is False
