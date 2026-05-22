from __future__ import annotations

from fastapi.testclient import TestClient
from app.core.db_access import execute_db, query_db
from tests.conftest import extract_csrf


def test_production_pages_renders(logged_client: TestClient):
    response = logged_client.get("/production")
    assert response.status_code == 200
    assert "Production" in response.text

    response_new = logged_client.get("/production/new")
    assert response_new.status_code == 200
    assert "Ajouter" in response_new.text or "Production" in response_new.text


def test_production_submit_success(logged_client: TestClient):
    # 1. Set up product & raw material
    p_id = execute_db("INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES ('Prod Prod', 'kg', 50.0, 100.0, 80.0)")
    r_id = execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES ('Raw Raw', 'kg', 100.0, 40.0, 50.0)")

    page = logged_client.get("/production/new")
    csrf_token = extract_csrf(page.text)

    try:
        # Submit valid production batch
        response = logged_client.post(
            "/production/new",
            data={
                "csrf_token": csrf_token,
                "finished_product_id": str(p_id),
                "output_quantity": "10.0",
                "production_date": "2026-05-22",
                "notes": "Testing success submit",
                "recipe_name": "Test Recipe",
                "save_recipe": "1",
                "raw_material_id[]": [str(r_id)],
                "quantity[]": ["20.0"]
            },
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/production"

        # Verify DB updates
        batch = query_db("SELECT * FROM production_batches WHERE finished_product_id = %s", (p_id,), one=True)
        assert batch is not None
        assert float(batch["output_quantity"]) == 10.0
        assert float(batch["production_cost"]) == 20.0 * 40.0 # 800 DA

        # Verify stock consumption
        raw_mat = query_db("SELECT stock_qty FROM raw_materials WHERE id = %s", (r_id,), one=True)
        assert float(raw_mat["stock_qty"]) == 80.0 # 100 - 20

        # Verify product stock addition
        prod = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (p_id,), one=True)
        assert float(prod["stock_qty"]) == 60.0 # 50 + 10

    finally:
        # Cleanup
        execute_db("DELETE FROM recipes WHERE finished_product_id = %s", (p_id,))
        execute_db("DELETE FROM production_batch_items WHERE raw_material_id = %s", (r_id,))
        execute_db("DELETE FROM production_batches WHERE finished_product_id = %s", (p_id,))
        execute_db("DELETE FROM finished_products WHERE id = %s", (p_id,))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (r_id,))


def test_production_submit_insufficient_stock(logged_client: TestClient):
    p_id = execute_db("INSERT INTO finished_products (name, default_unit, stock_qty) VALUES ('Prod Prod', 'kg', 50.0)")
    r_id = execute_db("INSERT INTO raw_materials (name, unit, stock_qty) VALUES ('Raw Raw', 'kg', 10.0)")

    page = logged_client.get("/production/new")
    csrf_token = extract_csrf(page.text)

    try:
        # Submit with quantity 20.0, which exceeds stock (10.0)
        response = logged_client.post(
            "/production/new",
            data={
                "csrf_token": csrf_token,
                "finished_product_id": str(p_id),
                "output_quantity": "5.0",
                "production_date": "2026-05-22",
                "notes": "Testing failure submit",
                "save_recipe": "0",
                "raw_material_id[]": [str(r_id)],
                "quantity[]": ["20.0"]
            },
            follow_redirects=False
        )
        # Should stay on page or redirect to /production/new with error
        assert response.status_code == 303
        assert response.headers["location"] == "/production/new"

        # Check no production batch was created
        batch = query_db("SELECT * FROM production_batches WHERE finished_product_id = %s", (p_id,), one=True)
        assert batch is None

    finally:
        # Cleanup
        execute_db("DELETE FROM finished_products WHERE id = %s", (p_id,))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (r_id,))


def test_delete_production(logged_client: TestClient):
    p_id = execute_db("INSERT INTO finished_products (name, default_unit, stock_qty, avg_cost) VALUES ('Prod Delete', 'kg', 60.0, 80.0)")
    r_id = execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost) VALUES ('Raw Delete', 'kg', 80.0, 40.0)")

    # 1. Manually create batch in DB
    batch_id = execute_db(
        "INSERT INTO production_batches (finished_product_id, output_quantity, production_cost, unit_cost, production_date) VALUES (%s, %s, %s, %s, %s)",
        (p_id, 10.0, 800.0, 80.0, "2026-05-22")
    )
    execute_db(
        "INSERT INTO production_batch_items (batch_id, raw_material_id, quantity, unit_cost_snapshot, line_cost) VALUES (%s, %s, %s, %s, %s)",
        (batch_id, r_id, 20.0, 40.0, 800.0)
    )

    page = logged_client.get("/production")
    csrf_token = extract_csrf(page.text)

    try:
        response = logged_client.post(
            f"/production/{batch_id}/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/production"

        # Check DB entry is gone
        batch = query_db("SELECT * FROM production_batches WHERE id = %s", (batch_id,), one=True)
        assert batch is None

        # Verify stock is reverted
        # raw material stock should increase back (80 + 20 = 100)
        raw_mat = query_db("SELECT stock_qty FROM raw_materials WHERE id = %s", (r_id,), one=True)
        assert float(raw_mat["stock_qty"]) == 100.0

        # finished product stock should decrease back (60 - 10 = 50)
        prod = query_db("SELECT stock_qty FROM finished_products WHERE id = %s", (p_id,), one=True)
        assert float(prod["stock_qty"]) == 50.0

    finally:
        # Cleanup if any
        execute_db("DELETE FROM production_batch_items WHERE batch_id = %s", (batch_id,))
        execute_db("DELETE FROM production_batches WHERE id = %s", (batch_id,))
        execute_db("DELETE FROM finished_products WHERE id = %s", (p_id,))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (r_id,))
