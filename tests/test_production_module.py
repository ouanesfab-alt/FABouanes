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
    productions_context,
    new_production_context,
)
from app.modules.production.web import parse_production_form


@pytest.mark.asyncio
async def test_production_repository_and_service_contexts():
    """Vérifie la récupération des contextes de production et formulaires."""
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
