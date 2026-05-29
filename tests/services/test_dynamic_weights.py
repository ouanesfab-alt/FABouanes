from __future__ import annotations

import pytest
from app.services.stock_service import qty_to_kg, unit_price_to_kg, create_purchase_record, reverse_purchase, create_sale_record, reverse_sale, recalc_raw_material_avg_cost
from app.core.db_access import query_db, execute_db

def test_qty_to_kg_helpers():
    # Test standard bag values (which default to 50kg)
    assert qty_to_kg(10.0, "sac") == 500.0
    assert qty_to_kg(2.5, "sac") == 125.0
    assert qty_to_kg(1.0, "sac (50kg)") == 50.0
    
    # Test custom bag values
    assert qty_to_kg(10.0, "sac (40kg)") == 400.0
    assert qty_to_kg(10.0, "sac (25kg)") == 250.0
    assert qty_to_kg(4.0, "sac 30 kg") == 120.0
    assert qty_to_kg(5.0, "sac de 12kg") == 60.0
    
    # Test non-bag values
    assert qty_to_kg(10.0, "kg") == 10.0
    assert qty_to_kg(10.0, "Qt") == 1000.0
    assert qty_to_kg(10.0, "unite") == 10.0
    assert qty_to_kg(10.0, None) == 10.0


def test_unit_price_to_kg_helpers():
    # Test standard bag values (which default to 50kg)
    assert unit_price_to_kg(2500.0, "sac") == 50.0
    assert unit_price_to_kg(2500.0, "sac (50kg)") == 50.0
    
    # Test custom bag values
    assert unit_price_to_kg(2000.0, "sac (40kg)") == 50.0
    assert unit_price_to_kg(1000.0, "sac (25kg)") == 40.0
    assert unit_price_to_kg(3000.0, "sac 30 kg") == 100.0
    
    # Test non-bag values
    assert unit_price_to_kg(65.0, "kg") == 65.0
    assert unit_price_to_kg(6500.0, "Qt") == 65.0
    assert unit_price_to_kg(10.0, None) == 10.0


@pytest.mark.asyncio
async def test_purchase_and_reverse_with_custom_weights(first_supplier_id, first_raw_material_id):
    # Reset stock and avg_cost of raw material
    execute_db("UPDATE raw_materials SET stock_qty = 100.0, avg_cost = 50.0 WHERE id = %s", (first_raw_material_id,))
    
    # Create purchase: 10 sacs of 40kg each = 400kg.
    # Unit price = 2000 per sac (which is 50 DA/kg).
    purchase_id = await create_purchase_record(
        supplier_id=first_supplier_id,
        item_kind_or_raw_id=first_raw_material_id,
        qty=10.0,
        unit_price=2000.0,
        purchase_date="2026-05-16",
        notes="Achat test sac 40kg",
        unit="sac (40kg)"
    )
    
    assert purchase_id > 0
    
    # Verify stock updated by 400kg (100 + 400 = 500)
    material = query_db("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    assert float(material["stock_qty"]) == 500.0
    # Expected avg_cost: (100 * 50 + 400 * 50) / 500 = 50.0
    assert float(material["avg_cost"]) == 50.0
    
    # Reverse the purchase
    ok = await reverse_purchase(purchase_id)
    assert ok is True
    
    # Verify stock is restored to 100.0
    material = query_db("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    assert float(material["stock_qty"]) == 100.0


@pytest.mark.asyncio
async def test_sale_and_reverse_with_custom_weights(first_client_id, first_product_id):
    # Reset stock and avg_cost of finished product
    execute_db("UPDATE finished_products SET stock_qty = 100.0, avg_cost = 80.0, sale_price = 100.0 WHERE id = %s", (first_product_id,))
    
    # Create sale: 2 sacs of 25kg each = 50kg.
    # Unit price = 3000 per sac (which is 120 DA/kg).
    kind, sale_id = await create_sale_record(
        client_id=first_client_id,
        item_kind="finished",
        item_id=first_product_id,
        qty=2.0,
        unit="sac (25kg)",
        unit_price=3000.0,
        sale_type="credit",
        sale_date="2026-05-16",
        notes="Vente test sac 25kg",
        amount_paid_input=0.0
    )
    
    assert kind == "finished"
    assert sale_id > 0
    
    # Verify stock updated: 100 - 50 = 50 kg
    product = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    assert float(product["stock_qty"]) == 50.0
    
    # Verify profit: total = 6000. cost_snapshot = 80.0. qty_kg = 50. profit = 6000 - 50 * 80 = 2000.
    sale = query_db("SELECT quantity, unit, unit_price, total, profit_amount FROM sales WHERE id = %s", (sale_id,), one=True)
    assert float(sale["quantity"]) == 2.0
    assert sale["unit"] == "sac (25kg)"
    assert float(sale["unit_price"]) == 3000.0
    assert float(sale["total"]) == 6000.0
    assert float(sale["profit_amount"]) == 2000.0
    
    # Reverse sale
    ok = await reverse_sale(kind, sale_id)
    assert ok is True
    
    # Verify stock is restored to 100.0
    product = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (first_product_id,), one=True)
    assert float(product["stock_qty"]) == 100.0


@pytest.mark.asyncio
async def test_recalc_raw_material_avg_cost_with_custom_weights(first_supplier_id, first_raw_material_id):
    # Reset stock and avg_cost of raw material to 0
    execute_db("UPDATE raw_materials SET stock_qty = 0.0, avg_cost = 0.0 WHERE id = %s", (first_raw_material_id,))
    # Clear any old purchases for this raw material to ensure clean calculation
    execute_db("DELETE FROM purchases WHERE raw_material_id = %s", (first_raw_material_id,))

    # Purchase 1: 10 sacs of 40kg each = 400kg. Price = 2000 per sac (50 DA/kg).
    p1 = await create_purchase_record(
        supplier_id=first_supplier_id,
        item_kind_or_raw_id=first_raw_material_id,
        qty=10.0,
        unit_price=2000.0,
        purchase_date="2026-05-16",
        notes="Achat 1",
        unit="sac (40kg)"
    )

    # Purchase 2: 5 sacs of 20kg each = 100kg. Price = 1600 per sac (80 DA/kg).
    p2 = await create_purchase_record(
        supplier_id=first_supplier_id,
        item_kind_or_raw_id=first_raw_material_id,
        qty=5.0,
        unit_price=1600.0,
        purchase_date="2026-05-16",
        notes="Achat 2",
        unit="sac (20kg)"
    )

    # Verify initial calculation during purchases:
    # Stock qty = 500.0 kg
    # Avg cost = (400 * 50 + 100 * 80) / 500 = 56.0 DA/kg
    material = query_db("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    assert float(material["stock_qty"]) == 500.0
    assert float(material["avg_cost"]) == 56.0

    # Call recalculate average cost explicitly
    await recalc_raw_material_avg_cost(first_raw_material_id)

    # Verify that the average cost remains correct (56.0 DA/kg)
    material_after = query_db("SELECT stock_qty, avg_cost FROM raw_materials WHERE id = %s", (first_raw_material_id,), one=True)
    assert float(material_after["stock_qty"]) == 500.0
    assert float(material_after["avg_cost"]) == 56.0
