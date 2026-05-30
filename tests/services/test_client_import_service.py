from __future__ import annotations

from unittest.mock import patch
import pytest
from app.core.db_access import execute_db, query_db
from app.modules.clients.service import ClientService
from app.core.async_db import AsyncSessionLocal


@pytest.fixture(autouse=True)
def cleanup_database():
    yield
    # Clean up test clients and their history
    execute_db("DELETE FROM client_history WHERE source = 'import_excel'")
    execute_db("DELETE FROM clients WHERE name IN ('Import Client New', 'Import Client Existing')")
    execute_db("DELETE FROM client_keys")


@pytest.mark.asyncio
async def test_import_client_nonexistent_id():
    mock_data = {
        "client_name": "Nonexistent Client",
        "solde_final": 0.0,
        "rows": []
    }
    with patch("app.modules.clients.service.parse_client_history_excel", return_value=mock_data):
        with pytest.raises(ValueError, match="Le client spécifié.*n'existe pas"):
            async with AsyncSessionLocal() as session:
                service = ClientService(session)
                await service.import_client_history_from_excel("dummy.xlsx", client_id=999999)


@pytest.mark.asyncio
async def test_import_client_new_client():
    mock_data = {
        "client_name": "Import Client New",
        "solde_final": 5000.0,
        "rows": [
            {
                "date": "2026-05-01",
                "designation": "Ancien solde",
                "montant_achat": 0.0,
                "montant_verse": 0.0,
                "solde_cumule": 5000.0,
                "ordre_import": 0
            }
        ]
    }

    with patch("app.modules.clients.service.parse_client_history_excel", return_value=mock_data):
        async with AsyncSessionLocal() as session:
            service = ClientService(session)
            result = await service.import_client_history_from_excel("dummy.xlsx", client_id=None)
        
        # Verify returned data
        assert result["client_name"] == "Import Client New"
        assert result["solde_final"] == 5000.0
        assert result["nb_lignes"] == 1
        assert result["client_id"] is not None

        # Verify client is created in DB
        client = query_db("SELECT * FROM clients WHERE id = %s", (result["client_id"],), one=True)
        assert client is not None
        assert client["name"] == "Import Client New"
        assert float(client["opening_credit"]) == 5000.0

        # Verify client_history insertion
        history = query_db("SELECT * FROM client_history WHERE client_id = %s", (result["client_id"],))
        assert len(history) == 1
        assert history[0]["designation"] == "Ancien solde"
        assert float(history[0]["solde_cumule"]) == 5000.0
        assert history[0]["source"] == "import_excel"


@pytest.mark.asyncio
async def test_import_client_existing_client_force_reimport():
    # 1. Manually insert client
    client_id = execute_db(
        "INSERT INTO clients (name, opening_credit) VALUES (%s, %s)",
        ("Import Client Existing", 1000.0)
    )
    
    # 2. Insert dummy old import history to test overwrite
    execute_db(
        """
        INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, solde_cumule, ordre_import, source)
        VALUES (%s, '2026-04-01', 'Old Row', 0, 0, 1000, 0, 'import_excel')
        """,
        (client_id,)
    )

    mock_data = {
        "client_name": "Import Client Existing",
        "solde_final": 2000.0,
        "rows": [
            {
                "date": "2026-05-02",
                "designation": "New Row",
                "montant_achat": 1000.0,
                "montant_verse": 0.0,
                "solde_cumule": 2000.0,
                "ordre_import": 0
            }
        ]
    }

    with patch("app.modules.clients.service.parse_client_history_excel", return_value=mock_data):
        # Run with force_reimport=True
        async with AsyncSessionLocal() as session:
            service = ClientService(session)
            result = await service.import_client_history_from_excel("dummy.xlsx", client_id=client_id, force_reimport=True)
        
        assert result["client_id"] == client_id
        assert result["solde_final"] == 2000.0

        # Verify old history is deleted, only new row exists
        history = query_db("SELECT * FROM client_history WHERE client_id = %s ORDER BY id", (client_id,))
        assert len(history) == 1
        assert history[0]["designation"] == "New Row"
        assert float(history[0]["solde_cumule"]) == 2000.0

        # Verify client's opening_credit updated to 2000.0
        client = query_db("SELECT opening_credit FROM clients WHERE id = %s", (client_id,), one=True)
        assert float(client["opening_credit"]) == 2000.0


@pytest.mark.asyncio
async def test_import_client_existing_client_no_reimport_error():
    # 1. Manually insert client
    client_id = execute_db(
        "INSERT INTO clients (name, opening_credit) VALUES (%s, %s)",
        ("Import Client Existing", 1000.0)
    )
    
    # 2. Insert dummy old import history to test overwrite
    execute_db(
        """
        INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, solde_cumule, ordre_import, source)
        VALUES (%s, '2026-04-01', 'Old Row', 0, 0, 1000, 0, 'import_excel')
        """,
        (client_id,)
    )

    mock_data = {
        "client_name": "Import Client Existing",
        "solde_final": 2000.0,
        "rows": []
    }

    with patch("app.modules.clients.service.parse_client_history_excel", return_value=mock_data):
        # Run with force_reimport=False -> should raise ValueError
        with pytest.raises(ValueError, match="Un historique Excel importé existe déjà"):
            async with AsyncSessionLocal() as session:
                service = ClientService(session)
                await service.import_client_history_from_excel("dummy.xlsx", client_id=client_id, force_reimport=False)
