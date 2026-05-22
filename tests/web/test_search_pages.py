from __future__ import annotations

from fastapi.testclient import TestClient
from app.core.db_access import execute_db


def test_search_unauthenticated(client: TestClient):
    response = client.get("/api/search?q=test")
    assert response.status_code == 401


def test_search_query_too_short(logged_client: TestClient):
    response = logged_client.get("/api/search?q=a")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_search_text_matching(logged_client: TestClient):
    # Insert temporary matching client, raw material, finished product, supplier
    c_id = execute_db("INSERT INTO clients (name, phone) VALUES ('SearchClientUnique', '0555999999')")
    r_id = execute_db("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price) VALUES ('SearchRawUnique', 'kg', 10, 5, 6)")
    p_id = execute_db("INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES ('SearchProdUnique', 'kg', 10, 15, 10)")
    s_id = execute_db("INSERT INTO suppliers (name, phone) VALUES ('SearchSupplierUnique', '0666999999')")

    try:
        # Search by client name
        response = logged_client.get("/api/search?q=SearchClientUnique")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1
        assert any(item["title"] == "SearchClientUnique" and item["type"] == "Client" for item in data)

        # Search by client phone
        response_phone = logged_client.get("/api/search?q=0555999999")
        assert response_phone.status_code == 200
        data_phone = response_phone.json()["data"]
        assert any(item["title"] == "SearchClientUnique" for item in data_phone)

        # Search by raw material name
        response_raw = logged_client.get("/api/search?q=SearchRawUnique")
        assert response_raw.status_code == 200
        data_raw = response_raw.json()["data"]
        assert any(item["title"] == "SearchRawUnique" and item["type"] == "Matière" for item in data_raw)

        # Search by finished product name
        response_prod = logged_client.get("/api/search?q=SearchProdUnique")
        assert response_prod.status_code == 200
        data_prod = response_prod.json()["data"]
        assert any(item["title"] == "SearchProdUnique" and item["type"] == "Produit" for item in data_prod)

        # Search by supplier name
        response_supp = logged_client.get("/api/search?q=SearchSupplierUnique")
        assert response_supp.status_code == 200
        data_supp = response_supp.json()["data"]
        assert any(item["title"] == "SearchSupplierUnique" and item["type"] == "Fournisseur" for item in data_supp)

    finally:
        # Cleanup
        execute_db("DELETE FROM clients WHERE id = %s", (c_id,))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (r_id,))
        execute_db("DELETE FROM finished_products WHERE id = %s", (p_id,))
        execute_db("DELETE FROM suppliers WHERE id = %s", (s_id,))


def test_search_date_matching(logged_client: TestClient):
    # Insert transaction entries with specific date: 2026-05-15
    # First, need matching client, supplier, product, raw mat
    c_id = execute_db("INSERT INTO clients (name) VALUES ('SearchDateClient')")
    s_id = execute_db("INSERT INTO suppliers (name) VALUES ('SearchDateSupplier')")
    p_id = execute_db("INSERT INTO finished_products (name, default_unit) VALUES ('SearchDateProduct', 'kg')")
    r_id = execute_db("INSERT INTO raw_materials (name, unit) VALUES ('SearchDateRaw', 'kg')")

    sale_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 1.0, 'kg', 100.0, 100.0, 'credit', 0, 100.0, '2026-05-15')
        """,
        (c_id, p_id)
    )

    purchase_id = execute_db(
        """
        INSERT INTO purchases (supplier_id, raw_material_id, quantity, unit, unit_price, total, purchase_date)
        VALUES (%s, %s, 2.0, 'kg', 50.0, 100.0, '2026-05-15')
        """,
        (s_id, r_id)
    )

    pay_id = execute_db(
        """
        INSERT INTO payments (client_id, amount, payment_date, payment_type, notes)
        VALUES (%s, 100.0, '2026-05-15', 'avance', 'Test Search Date')
        """,
        (c_id,)
    )

    try:
        # Query with exact YYYY-MM-DD
        response_exact = logged_client.get("/api/search?q=2026-05-15")
        assert response_exact.status_code == 200
        data_exact = response_exact.json()["data"]
        types_found = {item["type"] for item in data_exact}
        assert "Vente" in types_found
        assert "Achat" in types_found
        assert "Paiement" in types_found

        # Query with DD/MM/YYYY
        response_french = logged_client.get("/api/search?q=15/05/2026")
        assert response_french.status_code == 200
        assert len(response_french.json()["data"]) >= 3

        # Query with partial month/year: MM/YYYY
        response_partial = logged_client.get("/api/search?q=05/2026")
        assert response_partial.status_code == 200
        assert len(response_partial.json()["data"]) >= 3

    finally:
        # Cleanup
        execute_db("DELETE FROM sales WHERE id = %s", (sale_id,))
        execute_db("DELETE FROM purchases WHERE id = %s", (purchase_id,))
        execute_db("DELETE FROM payments WHERE id = %s", (pay_id,))
        execute_db("DELETE FROM clients WHERE id = %s", (c_id,))
        execute_db("DELETE FROM suppliers WHERE id = %s", (s_id,))
        execute_db("DELETE FROM finished_products WHERE id = %s", (p_id,))
        execute_db("DELETE FROM raw_materials WHERE id = %s", (r_id,))
