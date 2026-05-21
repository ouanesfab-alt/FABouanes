from __future__ import annotations

import time
import pytest
import threading
from app.core.db_access import db_transaction, execute_db, query_db
from app.core.exceptions import ValidationError
from app.services.stock_service import create_sale_record, create_purchase_record

def test_nested_transactions_savepoint():
    # Insert client in outer transaction
    with db_transaction():
        outer_client_id = execute_db(
            "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
            ("Client Outer", "0123456", "Outer Addr", "", 0)
        )
        assert outer_client_id > 0
        
        # Open a nested sub-transaction
        try:
            with db_transaction():
                # This should be rolled back to savepoint if exception occurs
                inner_client_id = execute_db(
                    "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
                    ("Client Inner", "987654", "Inner Addr", "", 0)
                )
                assert inner_client_id > 0
                raise ValueError("Intentionally roll back sub-transaction")
        except ValueError:
            # We caught the inner error in the outer transaction block
            pass

    # Verify results
    outer_client = query_db("SELECT * FROM clients WHERE id = %s", (outer_client_id,), one=True)
    assert outer_client is not None
    assert outer_client["name"] == "Client Outer"

    inner_client = query_db("SELECT * FROM clients WHERE name = %s", ("Client Inner",), one=True)
    assert inner_client is None  # Inner client must be rolled back!


def test_pessimistic_lock_concurrency():
    # Insert a product to test pessimistic locking
    product_id = execute_db(
        "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (%s, %s, %s, %s, %s)",
        ("Locking Test Product", "kg", 100.0, 150.0, 100.0)
    )
    assert product_id > 0

    barrier = threading.Barrier(2)
    timing_logs = []

    def run_locked_tx():
        with db_transaction():
            # Select with FOR UPDATE
            product = query_db("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (product_id,), one=True)
            timing_logs.append("thread_locked")
            # Wait for main thread to be ready to request the lock
            barrier.wait()
            # Hold lock for 0.5s to let main thread block on it
            time.sleep(0.5)
            # Perform subtraction
            execute_db("UPDATE finished_products SET stock_qty = stock_qty - 10 WHERE id = %s", (product_id,))
            timing_logs.append("thread_updated")
        timing_logs.append("thread_committed")

    # Start thread
    thread = threading.Thread(target=run_locked_tx)
    thread.start()

    # Wait for thread to acquire lock
    barrier.wait()
    time.sleep(0.1)

    # Main thread tries to acquire lock
    timing_logs.append("main_request_lock")
    with db_transaction():
        # This SELECT FOR UPDATE must block until the thread commits
        product_main = query_db("SELECT * FROM finished_products WHERE id = %s FOR UPDATE", (product_id,), one=True)
        timing_logs.append("main_locked")
        assert float(product_main["stock_qty"]) == 90.0  # Main thread must see the updated stock!
        execute_db("UPDATE finished_products SET stock_qty = stock_qty - 20 WHERE id = %s", (product_id,))

    thread.join()

    # Verify correct lock sequencing:
    # 1. thread acquires lock ("thread_locked")
    # 2. main requests lock ("main_request_lock")
    # 3. thread updates stock ("thread_updated")
    # 4. thread commits ("thread_committed")
    # 5. main gets lock ("main_locked")
    assert timing_logs.index("thread_locked") < timing_logs.index("main_request_lock")
    assert timing_logs.index("thread_committed") < timing_logs.index("main_locked")

    # Final stock check
    final_product = query_db("SELECT * FROM finished_products WHERE id = %s", (product_id,), one=True)
    assert float(final_product["stock_qty"]) == 70.0
