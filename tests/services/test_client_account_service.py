from __future__ import annotations

import json
import pytest
from app.core.db_access import execute_db, query_db
from app.services.client_account_service import (
    client_balance,
    get_open_credit_entries,
    apply_payment_to_entry,
    reverse_payment_allocations,
    create_payment_record,
)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    # Clean up operations created during tests
    execute_db("DELETE FROM payments")
    execute_db("DELETE FROM sales")
    execute_db("DELETE FROM raw_sales")
    execute_db("DELETE FROM clients WHERE name LIKE 'Acct%'")


def test_client_balance_nonexistent():
    assert client_balance(999999) == 0.0


def test_client_balance_and_payment_records():
    # 1. Create client
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    assert client_balance(client_id) == 0.0

    # 2. Get product & raw material IDs
    prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
    raw_mat = query_db("SELECT id FROM raw_materials LIMIT 1", one=True)
    assert prod is not None and raw_mat is not None
    prod_id = int(prod["id"])
    raw_mat_id = int(raw_mat["id"])

    # 3. Insert Finished Product sale (credit)
    sale_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 0.0, 1000.0, '2026-05-01')
        """,
        (client_id, prod_id)
    )

    # 4. Insert Raw Material sale (credit)
    raw_sale_id = execute_db(
        """
        INSERT INTO raw_sales (client_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 5.0, 'kg', 100.0, 500.0, 'credit', 0.0, 500.0, '2026-05-01')
        """,
        (client_id, raw_mat_id)
    )

    # Calculate balance (clients_with_stats view is updated, but if sqlite is used or view needs update, we check get_open_credit_entries)
    open_entries = get_open_credit_entries(client_id)
    assert len(open_entries) == 2
    assert {e["item_kind"] for e in open_entries} == {"finished", "raw"}

    # 5. Apply payment directly to finished product entry
    paid_finished = apply_payment_to_entry("finished", sale_id, 400.0)
    assert paid_finished == 400.0
    
    # Check balance due is updated
    sale_row = query_db("SELECT balance_due, amount_paid FROM sales WHERE id = %s", (sale_id,), one=True)
    assert float(sale_row["balance_due"]) == 600.0
    assert float(sale_row["amount_paid"]) == 400.0

    # 6. Apply payment directly to raw material entry
    paid_raw = apply_payment_to_entry("raw", raw_sale_id, 200.0)
    assert paid_raw == 200.0
    raw_sale_row = query_db("SELECT balance_due, amount_paid FROM raw_sales WHERE id = %s", (raw_sale_id,), one=True)
    assert float(raw_sale_row["balance_due"]) == 300.0
    assert float(raw_sale_row["amount_paid"]) == 200.0

    # Test invalid amount or nonexistent kind
    assert apply_payment_to_entry("finished", sale_id, -10) == 0.0
    assert apply_payment_to_entry("finished", 999999, 100.0) == 0.0
    assert apply_payment_to_entry("raw", 999999, 100.0) == 0.0


def test_create_payment_record_validation():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    
    # Negative/Zero amount raises ValueError
    with pytest.raises(ValueError, match="Le montant doit etre superieur a zero"):
        create_payment_record(client_id, 0.0, "2026-05-01", "Notes")

    # Nonexistent client ID raises ValueError
    with pytest.raises(ValueError, match="Client introuvable"):
        create_payment_record(999999, 100.0, "2026-05-01", "Notes")


def test_create_payment_record_avance():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    
    pay_id = create_payment_record(client_id, 500.0, "2026-05-01", "Avance test", payment_type="avance")
    assert pay_id is not None
    
    pay_row = query_db("SELECT * FROM payments WHERE id = %s", (pay_id,), one=True)
    assert pay_row["payment_type"] == "avance"
    assert float(pay_row["amount"]) == 500.0
    assert pay_row["notes"] == "Avance test"


def test_create_payment_record_linked():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
    prod_id = int(prod["id"])
    
    sale_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 0.0, 1000.0, '2026-05-01')
        """,
        (client_id, prod_id)
    )

    # Try linking to another client's credit -> should fail
    other_client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Other Client', 0.0)")
    with pytest.raises(ValueError, match="Cette creance ne correspond pas au client choisi"):
        create_payment_record(other_client_id, 200.0, "2026-05-01", "Link failure", sale_link=f"finished:{sale_id}")

    # Success link
    pay_id = create_payment_record(client_id, 400.0, "2026-05-01", "Versement lie", sale_link=f"finished:{sale_id}")
    assert pay_id is not None
    
    # Check sale was updated
    sale_row = query_db("SELECT balance_due, amount_paid FROM sales WHERE id = %s", (sale_id,), one=True)
    assert float(sale_row["balance_due"]) == 600.0
    
    # Check payment record has allocation meta
    pay_row = query_db("SELECT * FROM payments WHERE id = %s", (pay_id,), one=True)
    assert pay_row["sale_id"] == sale_id
    assert pay_row["sale_kind"] == "finished"
    meta = json.loads(pay_row["allocation_meta"])
    assert meta == [{"kind": "finished", "id": sale_id, "amount": 400.0}]


def test_create_payment_record_unlinked_automatic_allocation():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
    prod_id = int(prod["id"])
    
    # Insert two sales
    sale1_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 5.0, 'kg', 100.0, 500.0, 'credit', 0.0, 500.0, '2026-05-01')
        """,
        (client_id, prod_id)
    )
    sale2_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 0.0, 1000.0, '2026-05-02')
        """,
        (client_id, prod_id)
    )

    # Pay 800.0 -> should pay 500.0 to sale1 and 300.0 to sale2
    pay_id = create_payment_record(client_id, 800.0, "2026-05-01", "Versement global")
    assert pay_id is not None
    
    # Verify sales balance dues
    s1 = query_db("SELECT balance_due FROM sales WHERE id = %s", (sale1_id,), one=True)
    s2 = query_db("SELECT balance_due FROM sales WHERE id = %s", (sale2_id,), one=True)
    assert float(s1["balance_due"]) == 0.0
    assert float(s2["balance_due"]) == 700.0

    # Verify payment allocations
    pay_row = query_db("SELECT * FROM payments WHERE id = %s", (pay_id,), one=True)
    meta = json.loads(pay_row["allocation_meta"])
    assert len(meta) == 2
    assert meta[0] == {"kind": "finished", "id": sale1_id, "amount": 500.0}
    assert meta[1] == {"kind": "finished", "id": sale2_id, "amount": 300.0}


def test_create_payment_no_open_debt_error():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    
    # Client has no debt -> should raise ValueError
    with pytest.raises(ValueError, match="Aucune dette ouverte pour ce client"):
        create_payment_record(client_id, 100.0, "2026-05-01", "Unlinked payment with no debt")


def test_reverse_payment_allocations_meta():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
    prod_id = int(prod["id"])
    
    sale_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 0.0, 1000.0, '2026-05-01')
        """,
        (client_id, prod_id)
    )

    # 1. Apply payment
    pay_id = create_payment_record(client_id, 400.0, "2026-05-01", "Versement")
    
    # 2. Fetch payment row
    pay_row = query_db("SELECT * FROM payments WHERE id = %s", (pay_id,), one=True)
    
    # 3. Reverse allocations
    reverse_payment_allocations(pay_row)
    
    # 4. Verify sale balance is restored to 1000.0
    sale_row = query_db("SELECT balance_due, amount_paid FROM sales WHERE id = %s", (sale_id,), one=True)
    assert float(sale_row["balance_due"]) == 1000.0
    assert float(sale_row["amount_paid"]) == 0.0


def test_reverse_payment_allocations_legacy():
    client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Acct Test Client', 0.0)")
    prod = query_db("SELECT id FROM finished_products LIMIT 1", one=True)
    prod_id = int(prod["id"])
    
    sale_id = execute_db(
        """
        INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, sale_date)
        VALUES (%s, %s, 10.0, 'kg', 100.0, 1000.0, 'credit', 400.0, 600.0, '2026-05-01')
        """,
        (client_id, prod_id)
    )

    # Legacy payment row with no allocation_meta
    legacy_payment_row = {
        "allocation_meta": None,
        "payment_type": "versement",
        "sale_kind": "finished",
        "sale_id": sale_id,
        "raw_sale_id": None,
        "amount": 400.0,
    }

    reverse_payment_allocations(legacy_payment_row)
    
    # Verify sale balance is restored to 1000.0
    sale_row = query_db("SELECT balance_due, amount_paid FROM sales WHERE id = %s", (sale_id,), one=True)
    assert float(sale_row["balance_due"]) == 1000.0
    assert float(sale_row["amount_paid"]) == 0.0
