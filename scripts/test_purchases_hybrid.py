import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import bootstrap_and_migrate
from app.core.db_access import query_db, execute_db
from app.services.stock_service import create_purchase_record, reverse_purchase
from app.services.catalog_service import create_catalog_item_from_form, product_edit_context
from app.services.purchase_service import create_purchase_from_form, get_purchase

print("=" * 80)
print("[TEST] VERIFYING FABOUANES HYBRID PURCHASES & PREMIUM CATALOG ALTERATION")
print("=" * 80)

# 1. Bootstrap and migrate database
print("\n* Step 1: Bootstrapping and Migrating Database...")
bootstrap_and_migrate()
execute_db("DELETE FROM finished_products WHERE name = 'autre: Aliment Poussin Gold Bio'")
print("   - Schema migration and cleanup completed successfully!")

# 2. Add custom catalog item with prefixing check
print("\n* Step 2: Testing prefixing for custom product ('Autre : NOM')...")
form_custom = {
    "kind": "finished",
    "name": "Aliment Poussin Gold Bio",
    "unit": "kg",
    "stock_qty": "100",
    "avg_cost": "120",
    "sale_price": "180"
}
kind, product_id = create_catalog_item_from_form(form_custom)
product = query_db("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)
print(f"   - Product created: ID={product['id']}, Name='{product['name']}'")
assert product["name"] == "autre: Aliment Poussin Gold Bio", f"Expected 'autre: Aliment Poussin Gold Bio', got '{product['name']}'"

# Test stripping on edit context
context = product_edit_context(product_id)
print(f"   - Edit Context: Custom name value='{context['custom_name_value']}'")
assert context["custom_name_value"] == "Aliment Poussin Gold Bio", f"Expected stripped name, got '{context['custom_name_value']}'"

# 3. Create a Supplier
supplier = query_db("SELECT id FROM suppliers LIMIT 1", one=True)
if not supplier:
    supplier_id = execute_db("INSERT INTO suppliers (name, contact_name, phone) VALUES (%s, %s, %s)", ("Direct Agro", "Abderrahmane", "0555123456"))
else:
    supplier_id = supplier["id"]
print(f"   - Supplier found or created: ID={supplier_id}")

# 4. Perform finished product purchase
print("\n* Step 3: Registering finished product purchase...")
stock_before = float(product["stock_qty"])
qty_to_buy = 50.0
unit_price = 110.0

purchase_id = create_purchase_record(
    supplier_id=supplier_id,
    item_kind_or_raw_id="finished",
    qty=qty_to_buy,
    unit_price=unit_price,
    purchase_date="2026-05-18",
    notes="Achat premium test",
    unit="kg",
    item_id=product_id
)

product_after = query_db("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)
stock_after = float(product_after["stock_qty"])
print(f"   - Stock Before: {stock_before} kg | Stock After Purchase: {stock_after} kg (Expected: {stock_before + qty_to_buy} kg)")
assert stock_after == stock_before + qty_to_buy, f"Stock mismatch! Expected {stock_before + qty_to_buy}, got {stock_after}"

# 5. Check retrieval from purchase list and get_purchase
purchase_retrieved = get_purchase(purchase_id)
print(f"   - Purchase Item Name retrieved: '{purchase_retrieved['material_name']}'")
assert purchase_retrieved["material_name"] == "autre: Aliment Poussin Gold Bio", f"Expected product name, got '{purchase_retrieved['material_name']}'"

# 6. Reversal check
print("\n* Step 4: Reversing the purchase (Stock restoration)...")
ok = reverse_purchase(purchase_id)
assert ok, "Failed to reverse purchase"

product_reversed = query_db("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)
stock_reversed = float(product_reversed["stock_qty"])
print(f"   - Stock after reversal: {stock_reversed} kg (Expected original {stock_before} kg)")
assert stock_reversed == stock_before, f"Reversal stock mismatch! Expected {stock_before}, got {stock_reversed}"

print("\n" + "=" * 80)
print("SUCCESS: ALL HYBRID PURCHASES & PREFIXING TESTS PASSED WITH 100% SUCCESS!")
print("=" * 80)
sys.exit(0)
