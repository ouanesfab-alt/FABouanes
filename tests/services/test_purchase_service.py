from __future__ import annotations

import pytest
from app.services.purchase_service import create_purchase_from_form, delete_purchase_by_id
from app.repositories.purchase_repository import get_purchase
from app.core.exceptions import ValidationError

def test_create_purchase_validation_errors(first_supplier_id, first_raw_material_id):
    # Missing quantity
    form = {
        "supplier_id": str(first_supplier_id),
        "raw_material_id[]": [str(first_raw_material_id)],
        "quantity[]": [""],
        "unit[]": ["kg"],
        "unit_price[]": ["50"]
    }
    
    class FormMock:
        def __init__(self, data): self.data = data
        def get(self, k, default=None): return self.data.get(k, default)
        def getlist(self, k): return self.data.get(k, [])
    
    with pytest.raises(ValidationError):
        create_purchase_from_form(FormMock(form))

def test_create_and_delete_purchase(first_supplier_id, first_raw_material_id):
    form = {
        "supplier_id": str(first_supplier_id),
        "raw_material_id[]": [str(first_raw_material_id)],
        "quantity[]": ["20"],
        "unit[]": ["kg"],
        "unit_price[]": ["60"],
        "purchase_date": "2026-05-16"
    }
    
    class FormMock:
        def __init__(self, data): self.data = data
        def get(self, k, default=None): return self.data.get(k, default)
        def getlist(self, k): return self.data.get(k, [])

    result = create_purchase_from_form(FormMock(form))
    assert result["line_count"] == 1
    
    purchase_id = result["first_purchase_id"]
    
    purchase = get_purchase(purchase_id)
    assert purchase is not None
    assert float(purchase["display_quantity"]) == 20.0
    
    # Clean up
    assert delete_purchase_by_id(purchase_id) is True
    assert get_purchase(purchase_id) is None
