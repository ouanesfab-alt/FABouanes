from __future__ import annotations

import pytest
from app.services.sale_service import create_sale_from_form, delete_sale_by_id
from app.repositories.sale_repository import get_sale
from app.core.exceptions import ValidationError

def test_create_sale_validation_errors(first_client_id, first_product_id):
    # Missing quantity
    form = {
        "client_id": str(first_client_id),
        "item_key[]": [f"finished:{first_product_id}"],
        "quantity[]": [""],
        "unit[]": ["kg"],
        "unit_price[]": ["100"]
    }
    # Mocking form.getlist behavior
    class FormMock:
        def __init__(self, data): self.data = data
        def get(self, k, default=None): return self.data.get(k, default)
        def getlist(self, k): return self.data.get(k, [])
    
    with pytest.raises(ValidationError):
        create_sale_from_form(FormMock(form))

def test_create_and_delete_sale(first_client_id, first_product_id):
    form = {
        "client_id": str(first_client_id),
        "item_key[]": [f"finished:{first_product_id}"],
        "quantity[]": ["10"],
        "unit[]": ["kg"],
        "unit_price[]": ["150"],
        "sale_date": "2026-05-16"
    }
    
    class FormMock:
        def __init__(self, data): self.data = data
        def get(self, k, default=None): return self.data.get(k, default)
        def getlist(self, k): return self.data.get(k, [])

    result = create_sale_from_form(FormMock(form))
    assert result["line_count"] == 1
    
    sale_id = result["first_line_id"]
    kind = result["first_line_kind"]
    
    sale = get_sale(kind, sale_id)
    assert sale is not None
    assert float(sale["quantity"]) == 10.0
    
    # Clean up
    assert delete_sale_by_id(kind, sale_id) is True
    assert get_sale(kind, sale_id) is None
