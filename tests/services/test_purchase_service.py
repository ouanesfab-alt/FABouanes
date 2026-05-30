from __future__ import annotations

import pytest
from app.modules.purchases.service import PurchaseService
from app.modules.purchases.schemas_validation import PurchaseFormSchema
from app.repositories.purchase_repository import get_purchase
from app.core.exceptions import ValidationError
from app.core.async_db import AsyncSessionLocal
from pydantic import ValidationError as PydanticValidationError

@pytest.mark.asyncio
async def test_create_purchase_validation_errors(first_supplier_id, first_raw_material_id):
    # Missing quantity
    form = {
        "supplier_id": str(first_supplier_id),
        "raw_material_id[]": [f"raw:{first_raw_material_id}"],
        "quantity[]": [""],
        "unit[]": ["kg"],
        "unit_price[]": ["50"]
    }
    
    async with AsyncSessionLocal() as session:
        service = PurchaseService(session)
        schema = PurchaseFormSchema(**form)
        with pytest.raises(ValidationError):
            await service.create_purchase_from_form(schema)


@pytest.mark.asyncio
async def test_create_and_delete_purchase(first_supplier_id, first_raw_material_id):
    form = {
        "supplier_id": str(first_supplier_id),
        "raw_material_id[]": [f"raw:{first_raw_material_id}"],
        "quantity[]": ["20"],
        "unit[]": ["kg"],
        "unit_price[]": ["60"],
        "purchase_date": "2026-05-16"
    }
    
    async with AsyncSessionLocal() as session:
        service = PurchaseService(session)
        schema = PurchaseFormSchema(**form)
        result = await service.create_purchase_from_form(schema)
        assert result["line_count"] == 1
        
        purchase_id = result["first_purchase_id"]
        
        purchase = get_purchase(purchase_id)
        assert purchase is not None
        assert float(purchase["display_quantity"]) == 20.0
        
        # Clean up
        assert await service.delete_purchase_by_id(purchase_id) is True
        assert get_purchase(purchase_id) is None
