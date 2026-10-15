from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from fastapi.testclient import TestClient

from app.api.v1.offline import sync_operation, sync_operations_bulk
from app.core.exceptions import ValidationError
from app.main import app


@pytest.fixture
def api_client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_offline_sync_mutation_id_idempotency_hit():
    mutation_id = str(uuid.uuid4())
    req = MagicMock()
    req.headers = {"X-Idempotency-Key": mutation_id}
    req.json = MagicMock()

    async def mock_json():
        return {"type": "create_payment", "mutation_id": mutation_id, "payload": {}}

    req.json.side_effect = mock_json

    with patch("app.api.v1.offline.require_api_user"):
        with patch(
            "app.api.v1.offline.check_idempotency",
            return_value={"content": {"ok": True, "id": 42}, "status_code": 200},
        ) as mock_check:
            with patch("app.api.v1.offline.save_idempotency") as mock_save:
                res = await sync_operation(req, db=MagicMock(spec=AsyncSession))
                assert res.status_code == 200
                assert b'"ok":true' in res.body
                mock_check.assert_called_once_with(mutation_id, db=mock_check.call_args[1].get("db"))
                mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_offline_sync_creates_expense_and_saves_idempotency():
    mutation_id = str(uuid.uuid4())
    req = MagicMock()
    req.headers = {"X-Idempotency-Key": mutation_id}
    req.json = MagicMock()

    async def mock_json():
        return {
            "type": "create_expense",
            "mutation_id": mutation_id,
            "payload": {
                "date": "2026-06-15",
                "category": "transport",
                "description": "Frais de livraison",
                "amount": 120.50,
                "payment_method": "cash",
            },
        }

    req.json.side_effect = mock_json

    with patch("app.api.v1.offline.require_api_user"):
        with patch("app.api.v1.offline.check_idempotency", return_value=None):
            with patch("app.modules.expenses.service.add_expense", return_value=99) as mock_add_exp:
                with patch("app.api.v1.offline.save_idempotency") as mock_save:
                    res = await sync_operation(req, db=MagicMock(spec=AsyncSession))
                    assert res.status_code == 200
                    assert b'"ok":true' in res.body
                    assert b'"expense_id":99' in res.body
                    mock_add_exp.assert_called_once()
                    mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_offline_bulk_dead_letter_queue_isolation():
    """Vérifie qu'une opération en conflit dans un lot ne bloque pas les opérations valides."""
    mut_1 = str(uuid.uuid4())
    mut_2 = str(uuid.uuid4())

    req = MagicMock()
    req.json = MagicMock()

    async def mock_json():
        return {
            "operations": [
                {
                    "mutation_id": mut_1,
                    "type": "create_sale",
                    "payload": {"lines": []},  # Invalid, will raise ValidationError
                },
                {
                    "mutation_id": mut_2,
                    "type": "create_expense",
                    "payload": {
                        "date": "2026-06-15",
                        "category": "loyer",
                        "description": "Loyer mensuel",
                        "amount": 500.0,
                        "payment_method": "virement",
                    },
                },
            ]
        }

    req.json.side_effect = mock_json

    with patch("app.api.v1.offline.require_api_user"):
        with patch("app.api.v1.offline.check_idempotency", return_value=None):
            with patch("app.api.v1.offline.save_idempotency") as mock_save:
                with patch(
                    "app.modules.sales.service.SalesService.create_sale_from_form",
                    side_effect=ValidationError("La vente doit contenir au moins une ligne d'article."),
                ):
                    with patch("app.modules.expenses.service.add_expense", return_value=101):
                        res = await sync_operations_bulk(req, db=MagicMock(spec=AsyncSession))
                        assert res.status_code == 200
                        import json
                        body = json.loads(res.body.decode())
                        results = body["results"]
                        assert len(results) == 2

                        # Opération 1 marquée en conflit sans faire planter le lot
                        assert results[0]["mutation_id"] == mut_1
                        assert results[0]["status"] == "conflict"
                        assert results[0]["status_code"] == 422
                        assert "La vente doit contenir" in results[0]["error"]

                        # Opération 2 exécutée avec succès
                        assert results[1]["mutation_id"] == mut_2
                        assert results[1]["status"] == "synced"
                        assert results[1]["status_code"] == 200
                        assert results[1]["response"]["expense_id"] == 101

                        mock_save.assert_called_once()
