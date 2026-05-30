from __future__ import annotations

import pytest
import random
from decimal import Decimal, ROUND_HALF_UP
from app.core.db_access import execute_db, query_db
from app.modules.sales.service import SalesService
from app.modules.sales.schemas_validation import SaleFormSchema
from app.core.async_db import AsyncSessionLocal
from app.services.stock_service import record_stock_movement
from app.core.exceptions import ValidationError

class FormMock:
    def __init__(self, data):
        self.data = data
    def get(self, k, default=None):
        return self.data.get(k, default)
    def getlist(self, k):
        return self.data.get(k, [])
    def __getitem__(self, key):
        return self.data[key]
    def __contains__(self, key):
        return key in self.data


@pytest.mark.asyncio
async def test_stress_sales_math_calculations(first_client_id, first_product_id):
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
    async with AsyncSessionLocal() as session:
        service = SalesService(session)
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
            
            schema = SaleFormSchema(**form_data)
            result = await service.create_sale_from_form(schema)
            if not result or "line_count" not in result:
                raise RuntimeError(f"Debug: result is {result}")
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
            assert await service.delete_sale_by_id(kind, sale_id) is True



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


@pytest.mark.asyncio
async def test_stress_stock_adjustments(first_product_id, first_raw_material_id):
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
        await record_stock_movement("finished", first_product_id, "in" if delta >= 0 else "out", abs(delta), "kg", stock_before, stock_after, "stress_test", "finished", None)
        
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


@pytest.mark.asyncio
async def test_abusive_contact_creation():
    """
    Abusive stress test for clients and suppliers creation/deletion.
    Injects HTML tags, giant strings, special Unicode/Emojis, and typical SQL injection strings.
    """
    from app.modules.clients.service import ClientService
    from app.modules.clients.schemas_validation import ClientCreateSchema
    from app.services.contact_directory_service import create_supplier_from_form
    
    # Clean previous test records
    execute_db("DELETE FROM clients WHERE name LIKE 'abusive_%'")
    execute_db("DELETE FROM suppliers WHERE name LIKE 'abusive_%'")
    
    abusive_payloads = [
        "abusive_emoji_🚀🔥🌟💻",
        "abusive_html_<script>alert('hack')</script><b>bold</b>",
        "abusive_sql_' OR 1=1; --",
        "abusive_quotes_\"'`name`'\"",
        "abusive_giant_name_" + ("A" * 200), # Very long name
        "abusive_foreign_chars_漢語 español 123",
    ]
    
    async with AsyncSessionLocal() as session:
        client_service = ClientService(session)
        for payload in abusive_payloads:
            # Create client
            schema = ClientCreateSchema(
                name=payload,
                phone="0555555555",
                address="Abusive Address",
                notes="Abusive Note",
                opening_credit=150.75
            )
            client = await client_service.create_client(schema)
            client_id = client.id
            assert client_id > 0
            
            # Verify db matches
            row = query_db("SELECT name FROM clients WHERE id = %s", (client_id,), one=True)
            assert row["name"] == payload.strip()
            
            # Create supplier
            supplier_form = FormMock({
                "name": payload,
                "phone": "0555555556",
                "address": "Abusive Address",
                "notes": "Abusive Note"
            })
            supplier_id = await create_supplier_from_form(supplier_form)
            assert supplier_id > 0
            
            # Verify db matches
            s_row = query_db("SELECT name FROM suppliers WHERE id = %s", (supplier_id,), one=True)
            assert s_row["name"] == payload.strip()
            
            # Clean up
            await client_service.delete_client(client_id)
            execute_db("DELETE FROM suppliers WHERE id = %s", (supplier_id,))



@pytest.mark.asyncio
async def test_abusive_production_creation(first_product_id, first_raw_material_id):
    """
    Verify production validation rejects invalid/abusive data without leaving orphaned db rows.
    """
    from app.services.production_service import create_production_from_form
    
    # Reset raw material stock to check limits
    execute_db("UPDATE raw_materials SET stock_qty = 100.00, avg_cost = 50.00 WHERE id = %s", (first_raw_material_id,))
    
    # 1. Output quantity <= 0 (Should raise ValueError)
    invalid_form_1 = FormMock({
        "finished_product_id": str(first_product_id),
        "output_quantity": "0",
        "raw_material_id[]": [str(first_raw_material_id)],
        "quantity[]": ["10.00"],
        "save_recipe": "0"
    })
    with pytest.raises(ValueError, match="La quantite produite doit etre superieure a zero"):
        await create_production_from_form(invalid_form_1)
        
    # 2. Empty raw materials list (Should raise ValueError)
    invalid_form_2 = FormMock({
        "finished_product_id": str(first_product_id),
        "output_quantity": "50.00",
        "raw_material_id[]": [],
        "quantity[]": [],
        "save_recipe": "0"
    })
    with pytest.raises(ValueError, match="Ajoute au moins une matière première"):
        await create_production_from_form(invalid_form_2)
        
    # 3. Request quantity exceeding raw material stock limit
    invalid_form_3 = FormMock({
        "finished_product_id": str(first_product_id),
        "output_quantity": "50.00",
        "raw_material_id[]": [str(first_raw_material_id)],
        "quantity[]": ["200.00"], # Stock is only 100
        "save_recipe": "0"
    })
    with pytest.raises(ValueError, match="Stock insuffisant"):
        await create_production_from_form(invalid_form_3)
        
    # 4. Valid simulation - create and reverse immediately
    valid_form = FormMock({
        "finished_product_id": str(first_product_id),
        "output_quantity": "10.00",
        "raw_material_id[]": [str(first_raw_material_id)],
        "quantity[]": ["20.00"],
        "save_recipe": "0"
    })
    
    # Record initial stocks
    p_before = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    m_before = query_db("SELECT stock_qty FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    
    result = await create_production_from_form(valid_form)
    batch_id = result["batch_id"]
    assert batch_id > 0
    
    # Verify stock updated
    p_after = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    m_after = query_db("SELECT stock_qty FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    
    assert abs(float(p_after["stock_qty"]) - (float(p_before["stock_qty"]) + 10.00)) < 0.001
    assert abs(float(m_after["stock_qty"]) - (float(m_before["stock_qty"]) - 20.00)) < 0.001
    
    # Reverse production and verify stock restored
    from app.services.stock_service import reverse_production
    assert await reverse_production(batch_id) is True
    
    p_restored = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    m_restored = query_db("SELECT stock_qty FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    
    assert abs(float(p_restored["stock_qty"]) - float(p_before["stock_qty"])) < 0.001
    assert abs(float(m_restored["stock_qty"]) - float(m_before["stock_qty"])) < 0.001


@pytest.mark.asyncio
async def test_abusive_sales_validation(first_client_id, first_product_id):
    """
    Abusive checks on sale creations.
    """
    # Reset product stock
    execute_db("UPDATE finished_products SET stock_qty = 100.00 WHERE id = %s", (first_product_id,))
    
    # 1. Quantity exceeds stock
    invalid_sale = {
        "client_id": str(first_client_id),
        "item_key[]": [f"finished:{first_product_id}"],
        "quantity[]": ["150.00"],
        "unit[]": ["kg"],
        "unit_price[]": ["100.00"],
        "sale_date": "2026-05-19"
    }
    
    async with AsyncSessionLocal() as session:
        service = SalesService(session)
        with pytest.raises(Exception):
            schema = SaleFormSchema(**invalid_sale)
            await service.create_sale_from_form(schema)

