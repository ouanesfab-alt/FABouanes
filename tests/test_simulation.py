from __future__ import annotations

import time
import sys
import os
import pytest
from pathlib import Path
from io import BytesIO
from fastapi.testclient import TestClient

from app.core.storage import backup_database, restore_database_from, LOCAL_BACKUP_DIR
from app.core.db_access import query_db, execute_db

def test_scale_simulation(logged_client: TestClient, api_headers: dict):
    print("\n" + "="*60)
    print("STARTING LARGE SCALE USER SIMULATION (1000+ OPERATIONS)")
    print("="*60)
    sys.stdout.flush()

    # Track metrics
    start_time = time.perf_counter()
    operations_count = 0
    metrics = {}

    # Lists to store created entity IDs for referencing
    client_ids = []
    supplier_ids = []
    raw_material_ids = []
    product_ids = []
    
    # Store operation lists for deletion/modification
    purchase_ids = []
    sale_ids = []  # tuple of (kind, id)
    payment_ids = []
    production_ids = []

    # Helper function to track success
    def check_res(res, expected_codes=(200, 201)):
        nonlocal operations_count
        assert res.status_code in expected_codes, f"Request failed: {res.status_code} - {res.text}"
        operations_count += 1

    # =========================================================================
    # PHASE 1: CREATION OF ENTITIES (900 OPERATIONS)
    # =========================================================================
    print("\n--- PHASE 1: CREATING ENTITIES ---")
    sys.stdout.flush()

    # 1. Create 150 clients
    print("Creating 150 clients...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 151):
        res = logged_client.post(
            "/api/v1/clients",
            json={
                "name": f"Client Sim {i}",
                "phone": f"0550000{i:03d}",
                "address": f"Adresse Client {i}",
                "notes": f"Note client simulation {i}",
                "opening_credit": 0.0
            },
            headers=api_headers
        )
        check_res(res)
        client_ids.append(res.json()["data"]["id"])
    metrics["clients_creation"] = time.perf_counter() - t0
    print(f"Created 150 clients in {metrics['clients_creation']:.2f}s")

    # 2. Create 50 suppliers
    print("Creating 50 suppliers...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 51):
        res = logged_client.post(
            "/api/v1/suppliers",
            json={
                "name": f"Supplier Sim {i}",
                "phone": f"0660000{i:03d}",
                "address": f"Adresse Fournisseur {i}",
                "notes": f"Note fournisseur simulation {i}"
            },
            headers=api_headers
        )
        check_res(res)
        supplier_ids.append(res.json()["data"]["id"])
    metrics["suppliers_creation"] = time.perf_counter() - t0
    print(f"Created 50 suppliers in {metrics['suppliers_creation']:.2f}s")

    # 3. Create 50 raw materials
    print("Creating 50 raw materials...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 51):
        # Using a preset name to avoid prefixing with 'autre:' and keep test data clean
        preset_mats = ["Maïs", "Orge", "Son", "Soya", "CMV", "Phosphate", "Soja", "Sel", "Carbonate"]
        name = f"{preset_mats[i % len(preset_mats)]} Sim {i}"
        res = logged_client.post(
            "/api/v1/raw-materials",
            json={
                "name": name,
                "unit": "kg",
                "stock_qty": 1000.0,  # Initialize with stock to avoid negative stock alerts
                "avg_cost": 45.0 + (i % 10),
                "sale_price": 55.0 + (i % 10),
                "alert_threshold": 10.0
            },
            headers=api_headers
        )
        check_res(res)
        raw_material_ids.append(res.json()["data"]["id"])
    metrics["raw_materials_creation"] = time.perf_counter() - t0
    print(f"Created 50 raw materials in {metrics['raw_materials_creation']:.2f}s")

    # 4. Create 50 finished products
    print("Creating 50 finished products...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 51):
        preset_prods = ["Aliment Démarrage", "Aliment Croissance", "Aliment Finition", "Aliment Pondeuse"]
        name = f"{preset_prods[i % len(preset_prods)]} Sim {i}"
        res = logged_client.post(
            "/api/v1/finished-products",
            json={
                "name": name,
                "unit": "kg",
                "stock_qty": 500.0,  # Initialize with stock
                "sale_price": 120.0 + (i % 10),
                "avg_cost": 85.0 + (i % 10)
            },
            headers=api_headers
        )
        check_res(res)
        product_ids.append(res.json()["data"]["id"])
    metrics["products_creation"] = time.perf_counter() - t0
    print(f"Created 50 finished products in {metrics['products_creation']:.2f}s")

    # 5. Create 200 purchases (adds raw materials to stock)
    print("Creating 200 purchases...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 201):
        supplier_id = supplier_ids[i % len(supplier_ids)]
        raw_mat_id = raw_material_ids[i % len(raw_material_ids)]
        res = logged_client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": supplier_id,
                "amount_paid": 0.0,
                "payment_type": "credit",
                "purchase_date": "2026-05-21",
                "raw_material_id[]": [raw_mat_id],
                "quantity[]": [10.0 + (i % 5)],
                "unit[]": ["kg"],
                "unit_price[]": [40.0 + (i % 10)]
            },
            headers=api_headers
        )
        check_res(res)
        data = res.json()["data"]
        # Save purchase line ID
        if data["mode"] == "line":
            purchase_ids.append(data["purchase"]["id"])
        else:
            # Document mode: fetch document to get first line id
            doc_id = data["document_id"]
            doc_res = logged_client.get(f"/api/v1/purchase-documents/{doc_id}", headers=api_headers)
            doc_data = doc_res.json()["data"]
            purchase_ids.append(doc_data["lines"][0]["row_id"])
    metrics["purchases_creation"] = time.perf_counter() - t0
    print(f"Created 200 purchases in {metrics['purchases_creation']:.2f}s")

    # 6. Create 50 production batches (consumes raw materials, outputs finished products)
    print("Creating 50 production batches...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 51):
        product_id = product_ids[i % len(product_ids)]
        # Consume 2 different raw materials
        rm1 = raw_material_ids[(i * 2) % len(raw_material_ids)]
        rm2 = raw_material_ids[(i * 2 + 1) % len(raw_material_ids)]
        res = logged_client.post(
            "/api/v1/production-batches",
            json={
                "finished_product_id": product_id,
                "output_quantity": 5.0,
                "production_date": "2026-05-21",
                "notes": f"Production Simulation Batch {i}",
                "recipe_name": "",
                "save_recipe": 0,
                "raw_material_id[]": [rm1, rm2],
                "quantity[]": [2.0, 3.0]
            },
            headers=api_headers
        )
        check_res(res)
        production_ids.append(res.json()["data"]["batch"]["id"])
    metrics["productions_creation"] = time.perf_counter() - t0
    print(f"Created 50 productions in {metrics['productions_creation']:.2f}s")

    # 7. Create 200 sales (sells raw materials or products)
    print("Creating 200 sales...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 201):
        client_id = client_ids[i % len(client_ids)]
        if i % 2 == 0:
            # Sell finished product
            prod_id = product_ids[i % len(product_ids)]
            item_key = f"finished:{prod_id}"
        else:
            # Sell raw material
            rm_id = raw_material_ids[i % len(raw_material_ids)]
            item_key = f"raw:{rm_id}"
        
        res = logged_client.post(
            "/api/v1/sales",
            json={
                "client_id": client_id,
                "amount_paid": 0.0,
                "payment_type": "credit",
                "sale_date": "2026-05-21",
                "item_key[]": [item_key],
                "quantity[]": [1.0 + (i % 3)],
                "unit[]": ["kg"],
                "unit_price[]": [150.0 + (i % 10)]
            },
            headers=api_headers
        )
        check_res(res)
        data = res.json()["data"]
        if data["mode"] == "line":
            sale_ids.append((data["kind"], data["sale"]["id"]))
        else:
            # Document mode: fetch document to get first line kind/id
            doc_id = data["document_id"]
            doc_res = logged_client.get(f"/api/v1/sale-documents/{doc_id}", headers=api_headers)
            doc_data = doc_res.json()["data"]
            first_line = doc_data["lines"][0]
            sale_ids.append((first_line["row_kind"], first_line["row_id"]))
    metrics["sales_creation"] = time.perf_counter() - t0
    print(f"Created 200 sales in {metrics['sales_creation']:.2f}s")

    # 8. Create 150 payments
    print("Creating 150 payments...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(1, 151):
        client_id = client_ids[i % len(client_ids)]
        res = logged_client.post(
            "/api/v1/payments",
            json={
                "client_id": client_id,
                "amount": 50.0 + (i % 10) * 10,
                "payment_date": "2026-05-21",
                "payment_type": "avance",
                "sale_link": "",
                "notes": f"Avance Simulation {i}"
            },
            headers=api_headers
        )
        check_res(res)
        payment_ids.append(res.json()["data"]["payment"]["id"])
    metrics["payments_creation"] = time.perf_counter() - t0
    print(f"Created 150 payments in {metrics['payments_creation']:.2f}s")

    # =========================================================================
    # PHASE 2: MODIFICATIONS / UPDATES (150 OPERATIONS)
    # =========================================================================
    print("\n--- PHASE 2: MODIFYING ENTITIES ---")
    sys.stdout.flush()

    # 1. Modify 30 client cards
    print("Modifying 30 clients...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(30):
        c_id = client_ids[i]
        res = logged_client.put(
            f"/api/v1/clients/{c_id}",
            json={
                "name": f"Client Sim {i+1} Modified",
                "phone": f"0559999{i:03d}",
                "address": f"Adresse Client {i+1} Nouveau",
                "notes": f"Modifié par simulation",
                "opening_credit": 100.0
            },
            headers=api_headers
        )
        check_res(res)
    metrics["clients_modification"] = time.perf_counter() - t0

    # 2. Modify 20 supplier cards
    print("Modifying 20 suppliers...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        s_id = supplier_ids[i]
        res = logged_client.put(
            f"/api/v1/suppliers/{s_id}",
            json={
                "name": f"Supplier Sim {i+1} Modified",
                "phone": f"0669999{i:03d}",
                "address": f"Adresse Supplier {i+1} Nouveau",
                "notes": f"Modifié par simulation"
            },
            headers=api_headers
        )
        check_res(res)
    metrics["suppliers_modification"] = time.perf_counter() - t0

    # 3. Modify 20 raw materials parameters
    print("Modifying 20 raw materials...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        rm_id = raw_material_ids[i]
        res = logged_client.put(
            f"/api/v1/raw-materials/{rm_id}",
            json={
                "name": f"Maïs Mod {i}",
                "unit": "kg",
                "stock_qty": 1200.0,
                "avg_cost": 48.0,
                "sale_price": 58.0,
                "alert_threshold": 15.0
            },
            headers=api_headers
        )
        check_res(res)
    metrics["raw_materials_modification"] = time.perf_counter() - t0

    # 4. Modify 20 finished product parameters
    print("Modifying 20 finished products...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        prod_id = product_ids[i]
        res = logged_client.put(
            f"/api/v1/finished-products/{prod_id}",
            json={
                "name": f"Aliment Croissance Mod {i}",
                "default_unit": "kg",  # uses default_unit for update!
                "stock_qty": 600.0,
                "sale_price": 125.0,
                "avg_cost": 88.0
            },
            headers=api_headers
        )
        check_res(res)
    metrics["products_modification"] = time.perf_counter() - t0

    # 5. Modify 20 purchases
    print("Modifying 20 purchases...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        p_id = purchase_ids[i]
        raw_mat_id = raw_material_ids[i % len(raw_material_ids)]
        # Check if the purchase belongs to a document
        detail_res = logged_client.get(f"/api/v1/purchases/{p_id}", headers=api_headers)
        if detail_res.status_code == 200:
            purchase_data = detail_res.json()["data"]
            if purchase_data.get("document_id"):
                doc_id = purchase_data["document_id"]
                res = logged_client.put(
                    f"/api/v1/purchase-documents/{doc_id}",
                    json={
                        "supplier_id": supplier_ids[0],
                        "purchase_date": "2026-05-21",
                        "raw_material_id[]": [raw_mat_id],
                        "quantity[]": [12.0],
                        "unit[]": ["kg"],
                        "unit_price[]": [42.0]
                    },
                    headers=api_headers
                )
                check_res(res)
            else:
                res = logged_client.put(
                    f"/api/v1/purchases/{p_id}",
                    json={
                        "supplier_id": supplier_ids[0],
                        "purchase_date": "2026-05-21",
                        "raw_material_id[]": [raw_mat_id],
                        "quantity[]": [12.0],
                        "unit[]": ["kg"],
                        "unit_price[]": [42.0]
                    },
                    headers=api_headers
                )
                check_res(res)
    metrics["purchases_modification"] = time.perf_counter() - t0

    # 6. Modify 20 sales
    print("Modifying 20 sales...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        kind, s_id = sale_ids[i]
        # Skip doc type edits if it returns document required, or use PUT on sales details
        # Let's request the detail of sale, check if it belongs to a document
        detail_res = logged_client.get(f"/api/v1/sales/{kind}/{s_id}", headers=api_headers)
        if detail_res.status_code == 200:
            sale_data = detail_res.json()["data"]
            if sale_data.get("document_id"):
                # Modify via sale-documents API instead
                doc_id = sale_data["document_id"]
                res = logged_client.put(
                    f"/api/v1/sale-documents/{doc_id}",
                    json={
                        "client_id": client_ids[0],
                        "amount_paid": 20.0,
                        "payment_type": "credit",
                        "sale_date": "2026-05-21",
                        "item_key[]": [sale_data["item_key"]],
                        "quantity[]": [sale_data["quantity"]],
                        "unit[]": [sale_data["unit"]],
                        "unit_price[]": [sale_data["unit_price"] + 2.0]
                    },
                    headers=api_headers
                )
                check_res(res)
            else:
                res = logged_client.put(
                    f"/api/v1/sales/{kind}/{s_id}",
                    json={
                        "client_id": client_ids[0],
                        "amount_paid": 10.0,
                        "payment_type": "credit",
                        "sale_date": "2026-05-21",
                        "item_key[]": [sale_data["item_key"]],
                        "quantity[]": [sale_data["quantity"]],
                        "unit[]": [sale_data["unit"]],
                        "unit_price[]": [sale_data["unit_price"] + 5.0]
                    },
                    headers=api_headers
                )
                check_res(res)
    metrics["sales_modification"] = time.perf_counter() - t0

    # 7. Modify 20 payments
    print("Modifying 20 payments...")
    sys.stdout.flush()
    t0 = time.perf_counter()
    for i in range(20):
        pay_id = payment_ids[i]
        res = logged_client.put(
            f"/api/v1/payments/{pay_id}",
            json={
                "client_id": client_ids[0],
                "amount": 75.0,
                "payment_date": "2026-05-21",
                "payment_type": "avance",
                "sale_link": "",
                "notes": "Avance modifiée par simulation"
            },
            headers=api_headers
        )
        check_res(res)
    metrics["payments_modification"] = time.perf_counter() - t0
    print("Completed all 150 modifications successfully.")

    # =========================================================================
    # PHASE 3: DELETIONS / CANCELLATIONS (70 OPERATIONS)
    # =========================================================================
    print("\n--- PHASE 3: DELETING ENTITIES ---")
    sys.stdout.flush()

    # Create temporary isolated entities for safe deletion tests (no integrity errors)
    t0 = time.perf_counter()

    # 1. 10 Sale deletions
    print("Deleting 10 temporary sales...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/sales",
            json={
                "client_id": client_ids[0],
                "amount_paid": 0.0,
                "payment_type": "credit",
                "sale_date": "2026-05-21",
                "item_key[]": [f"finished:{product_ids[0]}"],
                "quantity[]": [1.0],
                "unit[]": ["kg"],
                "unit_price[]": [130.0]
            },
            headers=api_headers
        )
        check_res(res)
        temp_sale = res.json()["data"]
        if temp_sale["mode"] == "line":
            s_kind = temp_sale["kind"]
            s_id = temp_sale["sale"]["id"]
        else:
            # Document mode: fetch document to get first line kind/id
            doc_id = temp_sale["document_id"]
            doc_res = logged_client.get(f"/api/v1/sale-documents/{doc_id}", headers=api_headers)
            doc_data = doc_res.json()["data"]
            first_line = doc_data["lines"][0]
            s_kind = first_line["row_kind"]
            s_id = first_line["row_id"]
            
        del_res = logged_client.delete(f"/api/v1/sales/{s_kind}/{s_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 2. 10 Purchase deletions
    print("Deleting 10 temporary purchases...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": supplier_ids[0],
                "amount_paid": 0.0,
                "payment_type": "credit",
                "purchase_date": "2026-05-21",
                "raw_material_id[]": [raw_material_ids[0]],
                "quantity[]": [2.0],
                "unit[]": ["kg"],
                "unit_price[]": [40.0]
            },
            headers=api_headers
        )
        check_res(res)
        temp_data = res.json()["data"]
        if temp_data["mode"] == "line":
            temp_p_id = temp_data["purchase"]["id"]
        else:
            doc_id = temp_data["document_id"]
            doc_res = logged_client.get(f"/api/v1/purchase-documents/{doc_id}", headers=api_headers)
            doc_data = doc_res.json()["data"]
            temp_p_id = doc_data["lines"][0]["row_id"]
        
        del_res = logged_client.delete(f"/api/v1/purchases/{temp_p_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 3. 10 Payment deletions
    print("Deleting 10 temporary payments...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/payments",
            json={
                "client_id": client_ids[0],
                "amount": 10.0,
                "payment_date": "2026-05-21",
                "payment_type": "avance",
                "sale_link": "",
                "notes": "Temp payment"
            },
            headers=api_headers
        )
        check_res(res)
        temp_pay_id = res.json()["data"]["payment"]["id"]
        
        del_res = logged_client.delete(f"/api/v1/payments/{temp_pay_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 4. 10 Production deletions
    print("Deleting 10 temporary production batches...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/production-batches",
            json={
                "finished_product_id": product_ids[0],
                "output_quantity": 2.0,
                "production_date": "2026-05-21",
                "notes": "Temp production",
                "recipe_name": "",
                "save_recipe": 0,
                "raw_material_id[]": [raw_material_ids[0]],
                "quantity[]": [4.0]
            },
            headers=api_headers
        )
        check_res(res)
        temp_batch_id = res.json()["data"]["batch"]["id"]
        
        del_res = logged_client.delete(f"/api/v1/production-batches/{temp_batch_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 5. 10 Supplier deletions
    print("Deleting 10 temporary suppliers...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/suppliers",
            json={
                "name": f"Temp Supplier {i}",
                "phone": "00000000",
                "address": "Temp Address"
            },
            headers=api_headers
        )
        check_res(res)
        temp_s_id = res.json()["data"]["id"]
        
        del_res = logged_client.delete(f"/api/v1/suppliers/{temp_s_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 6. 10 Raw Material deletions
    print("Deleting 10 temporary raw materials...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/raw-materials",
            json={
                "name": f"Temp Material {i}",
                "unit": "kg",
                "stock_qty": 0.0,
                "avg_cost": 10.0,
                "sale_price": 12.0,
                "alert_threshold": 0.0
            },
            headers=api_headers
        )
        check_res(res)
        temp_rm_id = res.json()["data"]["id"]
        
        del_res = logged_client.delete(f"/api/v1/raw-materials/{temp_rm_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    # 7. 10 Finished Product deletions
    print("Deleting 10 temporary products...")
    sys.stdout.flush()
    for i in range(10):
        res = logged_client.post(
            "/api/v1/finished-products",
            json={
                "name": f"Temp Product {i}",
                "unit": "kg",
                "stock_qty": 0.0,
                "sale_price": 50.0,
                "avg_cost": 40.0
            },
            headers=api_headers
        )
        check_res(res)
        temp_fp_id = res.json()["data"]["id"]
        
        del_res = logged_client.delete(f"/api/v1/finished-products/{temp_fp_id}", headers=api_headers)
        check_res(del_res, expected_codes=(200, 204))

    metrics["deletions"] = time.perf_counter() - t0
    print(f"Deleted 70 temporary entities successfully in {metrics['deletions']:.2f}s")

    # =========================================================================
    # PHASE 4: DOCUMENT PRINTING VERIFICATION (50 OPERATIONS)
    # =========================================================================
    print("\n--- PHASE 4: VERIFYING PRINT FORMATS ---")
    sys.stdout.flush()
    t0 = time.perf_counter()

    # We will fetch print layouts for purchases, sales, payments, production, and client history
    print_ops = 0
    
    # 1. Print sales (HTML & PDF) — use indices 30+ to avoid stale IDs from Phase 2 modifications
    sale_print_start = 30
    for i in range(sale_print_start, min(sale_print_start + 10, len(sale_ids))):
        kind, s_id = sale_ids[i]
        # HTML Layout
        res = logged_client.get(f"/print/sale_finished/{s_id}") if kind == "finished" else logged_client.get(f"/print/sale_raw/{s_id}")
        check_res(res, expected_codes=(200,))
        print_ops += 1
        
        # PDF format
        res_pdf = logged_client.get(f"/print/sale_finished/{s_id}?format=pdf") if kind == "finished" else logged_client.get(f"/print/sale_raw/{s_id}?format=pdf")
        check_res(res_pdf, expected_codes=(200,))
        assert res_pdf.content.startswith(b"%PDF"), "Generated file does not look like a PDF"
        print_ops += 1

    # 2. Print purchases — use indices 30+ to avoid stale IDs from Phase 2 modifications
    purchase_print_start = 30
    for i in range(purchase_print_start, min(purchase_print_start + 10, len(purchase_ids))):
        p_id = purchase_ids[i]
        res = logged_client.get(f"/print/purchase/{p_id}")
        check_res(res, expected_codes=(200,))
        print_ops += 1
        
        res_pdf = logged_client.get(f"/print/purchase/{p_id}?format=pdf")
        check_res(res_pdf, expected_codes=(200,))
        assert res_pdf.content.startswith(b"%PDF"), "Generated file does not look like a PDF"
        print_ops += 1

    # 3. Print payments — use indices 25+ to avoid stale IDs from Phase 2 modifications
    payment_print_start = 25
    for i in range(payment_print_start, min(payment_print_start + 5, len(payment_ids))):
        pay_id = payment_ids[i]
        res = logged_client.get(f"/print/payment/{pay_id}")
        check_res(res, expected_codes=(200,))
        print_ops += 1
        
        res_pdf = logged_client.get(f"/print/payment/{pay_id}?format=pdf")
        check_res(res_pdf, expected_codes=(200,))
        assert res_pdf.content.startswith(b"%PDF"), "Generated file does not look like a PDF"
        print_ops += 1

    # 4. Print production batches
    for i in range(min(5, len(production_ids))):
        batch_id = production_ids[i]
        res = logged_client.get(f"/print/production/{batch_id}")
        check_res(res, expected_codes=(200,))
        print_ops += 1
        
        res_pdf = logged_client.get(f"/print/production/{batch_id}?format=pdf")
        check_res(res_pdf, expected_codes=(200,))
        assert res_pdf.content.startswith(b"%PDF"), "Generated file does not look like a PDF"
        print_ops += 1

    metrics["printing"] = time.perf_counter() - t0
    print(f"Verified {print_ops} print operations (HTML + PDF) in {metrics['printing']:.2f}s")

    # =========================================================================
    # PHASE 5: BACKUP & RESTORE CYCLES
    # =========================================================================
    print("\n--- PHASE 5: BACKUP & RESTORE CYCLES ---")
    sys.stdout.flush()
    t0 = time.perf_counter()

    # Backup & Restore Cycle 1
    print("Cycle 1: Backup, Modify data, Restore, Verify...")
    sys.stdout.flush()
    
    # 1. Capture snapshot before modifications
    backup_path = backup_database(reason="simulation_cycle_1", backup_type="manual")
    assert backup_path.exists() and backup_path.stat().st_size > 0
    operations_count += 1
    
    # 2. Modify a client name
    target_client_id = client_ids[0]
    res_orig = logged_client.get(f"/api/v1/clients/{target_client_id}", headers=api_headers)
    check_res(res_orig)
    original_name = res_orig.json()["data"]["name"]
    
    modified_name = "SIMULATOR_TEST_MODIFIED_NAME_C1"
    res_mod = logged_client.put(
        f"/api/v1/clients/{target_client_id}",
        json={
            "name": modified_name,
            "phone": "0550000000",
            "address": "Mod",
            "opening_credit": 0.0
        },
        headers=api_headers
    )
    check_res(res_mod)
    
    # Check that client name is modified
    res_verify = logged_client.get(f"/api/v1/clients/{target_client_id}", headers=api_headers)
    check_res(res_verify)
    assert res_verify.json()["data"]["name"] == modified_name
    
    # 3. Restore the database from snapshot
    restore_database_from(str(backup_path))
    operations_count += 1
    
    # 4. Verify client is restored to original name
    res_restored = logged_client.get(f"/api/v1/clients/{target_client_id}", headers=api_headers)
    check_res(res_restored)
    assert res_restored.json()["data"]["name"] == original_name
    print("Cycle 1 completed successfully. Client name reverted.")
    sys.stdout.flush()

    # Backup & Restore Cycle 2
    print("Cycle 2: Backup, Delete data, Restore, Verify...")
    sys.stdout.flush()
    
    # 1. Capture snapshot before deletions
    backup_path_2 = backup_database(reason="simulation_cycle_2", backup_type="manual")
    assert backup_path_2.exists() and backup_path_2.stat().st_size > 0
    operations_count += 1
    
    # 2. Create and then delete a new client (or check that a new entity disappears after restore)
    res_c2 = logged_client.post(
        "/api/v1/clients",
        json={
            "name": "Client C2 Deleted After Restore",
            "phone": "0551111111",
            "address": "C2",
            "opening_credit": 0.0
        },
        headers=api_headers
    )
    check_res(res_c2)
    c2_id = res_c2.json()["data"]["id"]
    
    # Verify client exists
    res_verify_c2 = logged_client.get(f"/api/v1/clients/{c2_id}", headers=api_headers)
    check_res(res_verify_c2)
    
    # 3. Restore the database from second snapshot (before client was created)
    restore_database_from(str(backup_path_2))
    operations_count += 1
    
    # 4. Verify client is gone (returns 404)
    res_gone = logged_client.get(f"/api/v1/clients/{c2_id}", headers=api_headers)
    assert res_gone.status_code == 404
    operations_count += 1
    print("Cycle 2 completed successfully. Temporary client reverted to non-existence.")
    sys.stdout.flush()

    # Cleanup backup files
    backup_path.unlink(missing_ok=True)
    backup_path_2.unlink(missing_ok=True)

    metrics["backup_restore"] = time.perf_counter() - t0

    # =========================================================================
    # SUMMARY & PERFORMANCE RESULTS
    # =========================================================================
    total_time = time.perf_counter() - start_time
    throughput = operations_count / total_time
    
    print("\n" + "="*60)
    print("SIMULATION SUMMARY")
    print("="*60)
    print(f"Total Operations Executed: {operations_count}")
    print(f"Total Duration:            {total_time:.2f} seconds")
    print(f"Global Throughput:         {throughput:.2f} operations/sec")
    print("-"*60)
    print("Detailed metrics (time in seconds):")
    for step, duration in metrics.items():
        print(f" - {step:<25}: {duration:.2f}s")
    print("="*60 + "\n")
    sys.stdout.flush()

    assert operations_count >= 1000
