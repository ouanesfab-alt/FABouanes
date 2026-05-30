from __future__ import annotations

import pytest
from app.modules.sales.service import SalesService
from app.modules.sales.schemas_validation import SaleFormSchema
from app.repositories.sale_repository import get_sale
from app.core.exceptions import ValidationError
from app.core.async_db import AsyncSessionLocal
from pydantic import ValidationError as PydanticValidationError

@pytest.mark.asyncio
async def test_create_sale_validation_errors(first_client_id, first_product_id):
    # Missing quantity
    form = {
        "client_id": str(first_client_id),
        "item_key[]": [f"finished:{first_product_id}"],
        "quantity[]": [""],
        "unit[]": ["kg"],
        "unit_price[]": ["100"]
    }
    
    async with AsyncSessionLocal() as session:
        service = SalesService(session)
        schema = SaleFormSchema(**form)
        with pytest.raises(ValidationError):
            await service.create_sale_from_form(schema)


@pytest.mark.asyncio
async def test_create_and_delete_sale(first_client_id, first_product_id):
    form = {
        "client_id": str(first_client_id),
        "item_key[]": [f"finished:{first_product_id}"],
        "quantity[]": ["10"],
        "unit[]": ["kg"],
        "unit_price[]": ["150"],
        "sale_date": "2026-05-16"
    }
    
    async with AsyncSessionLocal() as session:
        service = SalesService(session)
        schema = SaleFormSchema(**form)
        result = await service.create_sale_from_form(schema)
        assert result["line_count"] == 1
        
        sale_id = result["first_line_id"]
        kind = result["first_line_kind"]
        
        sale = get_sale(kind, sale_id)
        assert sale is not None
        assert float(sale["quantity"]) == 10.0
        
        # Clean up
        assert await service.delete_sale_by_id(kind, sale_id) is True
        assert get_sale(kind, sale_id) is None
