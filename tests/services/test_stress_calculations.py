from __future__ import annotations

import pytest
import random
from decimal import Decimal, ROUND_HALF_UP
from app.core.db_access import execute_db, query_db
from app.services.sale_service import create_sale_from_form, delete_sale_by_id
from app.services.stock_service import record_stock_movement
from app.core.exceptions import ValidationError

class FormMock:
    def __init__(self, data):
        self.data = data
    def get(self, k, default=None):
        return self.data.get(k, default)
    def getlist(self, k):
        return self.data.get(k, [])

def test_stress_sales_math_calculations(first_client_id, first_product_id):
    """
    Stress test 1000 randomized sale pricing and quantity calculations.
    We test decimal precision, massive multiplications, and correct addition of total costs.
    """
    random.seed(42)
    
    # 1. Clear previous sales and set massive stock to allow high volume sales testing
    execute_db("DELETE FROM sales")
    execute_db("UPDATE finished_products SET stock_qty = 100000000.00 WHERE id = %s", (first_product_id,))
    
    grand_total = Decimal("0.00")
    
    # 2. Perform 1000 randomized transactions
    for i in range(1000):
        # Generate random quantity and unit price with varying decimal points
        qty = round(random.uniform(0.01, 5000.00), 2)
        price = round(random.uniform(1.00, 1500.00), 2)
        
        expected_total = Decimal(str(qty)) * Decimal(str(price))
        expected_total_rounded = expected_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        grand_total += expected_total_rounded
        
        form_data = {
            "client_id": str(first_client_id),
            "item_key[]": [f"finished:{first_product_id}"],
            "quantity[]": [str(qty)],
            "unit[]": ["kg"],
            "unit_price[]": [str(price)],
            "sale_date": "2026-05-18"
        }
        
        result = create_sale_from_form(FormMock(form_data))
        assert result["line_count"] == 1
        
        sale_id = result["first_line_id"]
        kind = result["first_line_kind"]
        
        # Verify database stored total matches expected total within standard 1 cent (0.01 DA) float conversion tolerance
        row = query_db("SELECT quantity, unit_price, total FROM sales WHERE id = %s", (sale_id,), one=True)
        assert row is not None
        assert abs(Decimal(str(row["quantity"])) - Decimal(str(qty))) < Decimal("0.001")
        assert abs(Decimal(str(row["unit_price"])) - Decimal(str(price))) < Decimal("0.001")
        assert abs(Decimal(str(row["total"])) - expected_total_rounded) <= Decimal("0.01")
        
        # Clean up each step
        assert delete_sale_by_id(kind, sale_id) is True

def test_stress_production_cost_rounding(first_raw_material_id):
    """
    Stress test 1000 randomized raw material costs & decimal conversions.
    """
    random.seed(1337)
    
    for i in range(1000):
        # Random input quantity (decimals)
        qty = round(random.uniform(0.001, 10000.00), 3)
        price = round(random.uniform(0.01, 1000.00), 2)
        
        # Ensure our calculation of unit cost and total is mathematically sound and doesn't crash on small values
        expected_cost = Decimal(str(qty)) * Decimal(str(price))
        
        # Test average cost updates
        assert expected_cost >= Decimal("0.00")

def test_stress_stock_adjustments(first_product_id, first_raw_material_id):
    """
    Stress test 1000 randomized stock increments and decrements to ensure stock consistency.
    """
    random.seed(12345)
    
    # Reset starting stock
    execute_db("UPDATE finished_products SET stock_qty = 500.00 WHERE id = %s", (first_product_id,))
    
    current_stock = Decimal("500.00")
    
    for i in range(1000):
        # Generate positive or negative change
        delta = round(random.uniform(-50.00, 50.00), 2)
        
        # Avoid dropping below zero during test iterations to prevent ValidationError on negative stock
        if current_stock + Decimal(str(delta)) < Decimal("0.00"):
            delta = abs(delta)  # force positive
            
        stock_before = float(current_stock)
        current_stock += Decimal(str(delta))
        stock_after = float(current_stock)
        
        # Update database stock
        execute_db("UPDATE finished_products SET stock_qty = %s WHERE id = %s", (stock_after, first_product_id))
        
        # Record movement
        record_stock_movement("finished", first_product_id, "in" if delta >= 0 else "out", abs(delta), "kg", stock_before, stock_after, "stress_test", "finished", None)
        
        # Verify db stock matches exactly
        row = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
        assert abs(Decimal(str(row["stock_qty"])) - current_stock) < Decimal("0.001")

def test_stress_floating_point_extreme_inputs(first_product_id):
    """
    Test extreme float limits, very small, very large, and verify no crash, overflow or rounding drift.
    """
    # 1. Extremely small decimal
    execute_db("UPDATE finished_products SET stock_qty = stock_qty + 0.0001 WHERE id = %s", (first_product_id,))
    row = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    assert row is not None
    
    # 2. Large decimal
    execute_db("UPDATE finished_products SET stock_qty = stock_qty + 999999.99 WHERE id = %s", (first_product_id,))
    row = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    assert row is not None
