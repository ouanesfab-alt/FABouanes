# -*- coding: utf-8 -*-
"""
Tests fonctionnels et unitaires pour le module Production (Lot 3).
"""
from __future__ import annotations

import pytest
from app.modules.production.repository import (
    list_production_page_context,
    production_form_context,
)
from app.modules.production.service import (
    new_production_context,
)
from app.modules.production.web import parse_production_form


@pytest.mark.asyncio
async def test_production_repository_and_service_contexts():
    """Vérifie la récupération des contextes de production et formulaires."""
    from unittest.mock import patch, MagicMock, AsyncMock


    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_res = MagicMock()
    mock_res.scalars.return_value = mock_scalars
    mock_res.fetchall.return_value = []
    mock_res.scalar.return_value = 0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_res)

    with patch("app.modules.production.repository.get_async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__.return_value = mock_session

        form_ctx = await production_form_context()
        assert isinstance(form_ctx, dict)
        assert "raw_materials" in form_ctx
        assert "products" in form_ctx
        assert "recipes" in form_ctx

        new_ctx = await new_production_context()
        assert "raw_materials" in new_ctx

        list_ctx = await list_production_page_context({"page": "1", "q": ""})
        assert "productions" in list_ctx
        assert "pagination" in list_ctx



def test_parse_production_form_helper():
    """Vérifie le parsing des formulaires HTML de production."""
    class DummyForm(dict):
        def getlist(self, key):
            if key == "raw_material_id[]":
                return ["1", "2"]
            if key == "quantity[]":
                return ["10.5", "5.0"]
            return []

    form_data = DummyForm({
        "finished_product_id": "5",
        "output_quantity": "100.0",
        "production_date": "2026-07-31",
        "notes": "Test production lot 3",
    })

    parsed = parse_production_form(form_data)
    assert parsed["finished_product_id"] == 5
    assert parsed["output_quantity"] == 100.0
    assert parsed["production_date"] == "2026-07-31"
    assert len(parsed["items"]) == 2
    assert parsed["items"][0]["raw_material_id"] == 1
    assert parsed["items"][0]["quantity"] == 10.5


@pytest.mark.asyncio
async def test_production_yield_and_shrinkage_calculation():
    """Vérifie le calcul exact de la freinte et du rendement en Decimal."""
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.modules.production.service import _create_production_from_form_impl

    mock_db = AsyncMock()

    # Finished product mock
    prod_mock = MagicMock()
    prod_mock.model_dump.return_value = {"id": 1, "name": "Aliment Bovin", "stock_qty": Decimal("500"), "avg_cost": Decimal("40")}
    res_prod = MagicMock()
    res_prod.scalar_one_or_none.return_value = prod_mock

    # Raw material mock (1000 kg total consumed)
    raw1 = MagicMock()
    raw1.model_dump.return_value = {"id": 10, "name": "Maïs", "stock_qty": Decimal("2000"), "avg_cost": Decimal("30")}
    raw2 = MagicMock()
    raw2.model_dump.return_value = {"id": 11, "name": "Soja", "stock_qty": Decimal("1000"), "avg_cost": Decimal("50")}
    res_mat = MagicMock()
    res_mat.scalars.return_value.all.return_value = [raw1, raw2]

    # Batch return mock
    batch_mock = MagicMock()
    batch_mock.model_dump.return_value = {
        "id": 99,
        "finished_product_id": 1,
        "output_quantity": Decimal("980.00"),
        "total_raw_quantity": Decimal("1000.00"),
        "waste_quantity": Decimal("20.00"),
        "yield_rate": Decimal("98.00"),
    }
    res_batch = MagicMock()
    res_batch.scalar_one_or_none.return_value = batch_mock

    mock_db.execute = AsyncMock(side_effect=[res_prod, res_mat, res_batch])

    form = {
        "finished_product_id": 1,
        "output_quantity": "980",  # 980 kg produced from 1000 kg ingredients => 20 kg waste (2% freinte)
        "production_date": "2026-05-15",
        "notes": "Test freinte",
        "save_recipe": "0",
        "raw_material_id[]": [10, 11],
        "quantity[]": ["600", "400"],
    }

    with patch("app.modules.production.service.apply_raw_material_consumption", new_callable=AsyncMock), \
         patch("app.modules.production.service.apply_finished_production", new_callable=AsyncMock), \
         patch("app.modules.production.service.log_activity"), \
         patch("app.modules.production.service.audit_event"), \
         patch("app.modules.production.service.invalidate_sellable_items_cache"), \
         patch("app.modules.production.service.mark_backup_needed"):

        result = await _create_production_from_form_impl(form, mock_db)

        assert result["total_raw_quantity"] == Decimal("1000")
        assert result["waste_quantity"] == Decimal("20")
        assert result["yield_rate"] == Decimal("98.00")

