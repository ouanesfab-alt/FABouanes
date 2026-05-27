from __future__ import annotations

from app.core.db_access import execute_db, query_db
from app.repositories.transaction_repository import list_transactions_context


def test_sales_page_renders(logged_client):
    response = logged_client.get("/operations?type=sale")
    assert response.status_code == 200
    assert "Operations" in response.text
    assert "Ventes" in response.text


def test_sale_form_renders(logged_client):
    response = logged_client.get("/operations/sales/new")
    assert response.status_code == 200
    assert "Lignes de vente" in response.text or "Ajouter une ligne" in response.text


def test_transactions_date_sort_keeps_newest_same_day_sales_first(logged_client, first_client_id):
    product = query_db("SELECT id FROM finished_products ORDER BY id LIMIT 1", one=True)
    assert product is not None
    product_id = int(product["id"])
    sale_ids = []
    for quantity in (11, 12, 13):
        total = quantity * 100
        sale_ids.append(
            execute_db(
                """
                INSERT INTO sales (
                    client_id, finished_product_id, quantity, unit, unit_price, total,
                    sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount,
                    sale_date, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (first_client_id, product_id, quantity, "kg", 100, total, "credit", 0, total, 70, total - (quantity * 70), "2035-05-08", "sort test"),
            )
        )

    context = list_transactions_context({"type": "sale", "sort": "date", "direction": "desc", "page_size": "200"})
    ordered_ids = [
        int(row["id"])
        for row in context["transactions"]
        if row["tx_kind"] == "sale_finished" and int(row["id"]) in sale_ids
    ]
    assert ordered_ids == list(reversed(sale_ids))
