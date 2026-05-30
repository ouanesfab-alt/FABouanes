from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.clients.service import ClientService, _format_quantity
from app.modules.clients.schemas_validation import ClientCreateSchema, ClientUpdateSchema
from app.core.models import Client
from pydantic import ValidationError as PydanticValidationError


# ---------------------------------------------------------------------------
# ClientCreateSchema & ClientUpdateSchema validation
# ---------------------------------------------------------------------------

def test_client_create_schema_invalid_credit() -> None:
    with pytest.raises((PydanticValidationError, ValueError)):
        ClientCreateSchema(name="Test", phone="0555", address="addr", notes="", opening_credit="-10")


def test_client_create_schema_empty_name() -> None:
    with pytest.raises((PydanticValidationError, ValueError)):
        ClientCreateSchema(name="", phone="0555", address="addr", notes="")


def test_client_create_schema_valid() -> None:
    schema = ClientCreateSchema(name="Test Client", phone="0555", address="addr", notes="", opening_credit=100.0)
    assert schema.name == "Test Client"
    assert schema.opening_credit == 100.0


# ---------------------------------------------------------------------------
# _format_quantity helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        (0, "0"),
        (1.50, "1.5"),
        (10.00, "10"),
        (3.14, "3.14"),
        (None, "0"),
        ("abc", "0.00"),
        ("", "0"),
    ],
)
def test_format_quantity(value, expected) -> None:
    """Should format numeric values removing trailing zeros, and handle invalid input."""
    assert _format_quantity(value) == expected


# ---------------------------------------------------------------------------
# ClientService mocks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_client_not_found() -> None:
    session = AsyncMock()
    service = ClientService(session)
    service.repo = AsyncMock()
    service.repo.get_by_id.return_value = None

    result = await service.get_client(999)
    assert result is None


@pytest.mark.asyncio
async def test_delete_client_success() -> None:
    session = AsyncMock()
    service = ClientService(session)
    service.repo = AsyncMock()
    
    client = MagicMock()
    client.id = 5
    client.model_dump.return_value = {"id": 5}
    
    service.repo.get_by_id.return_value = client
    service.repo.delete.return_value = True
    
    with patch("app.modules.clients.service.emit") as mock_emit:
        result = await service.delete_client(5)
        assert result is True
        service.repo.delete.assert_called_once_with(5)
        mock_emit.assert_called_once()



@pytest.mark.asyncio
async def test_preview_clients_from_files() -> None:
    session = AsyncMock()
    service = ClientService(session)
    
    parsed = {
        "rows": [{"name": "C1", "status": "create", "filename": "c1.xlsx"}],
        "errors": [],
        "duplicates": [],
    }
    
    with patch.object(service, "_parse_client_import_files", new_callable=AsyncMock, return_value=parsed), \
         patch.object(service, "_save_client_import_preview", return_value="tok_abc123"):
        
        result = await service.preview_clients_from_files(["file1"])
        assert result["token"] == "tok_abc123"
        assert result["created"] == 1
