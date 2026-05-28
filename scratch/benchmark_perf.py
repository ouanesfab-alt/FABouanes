from __future__ import annotations

import os
import sys
import time

# Ensure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.db import connect_database

def run_benchmark():
    print("Initializing Database Connection for Performance Benchmark...")
    conn = connect_database(settings.database_url)
    
    try:
        # Create test tables/data
        print("Cleaning up any previous benchmark test data...")
        conn.execute("DELETE FROM sales WHERE notes = 'BENCHMARK_TEST'")
        conn.execute("DELETE FROM finished_products WHERE name = 'BENCHMARK_PRODUCT'")
        conn.execute("DELETE FROM clients WHERE name = 'BENCHMARK_CLIENT'")
        conn.commit()

        # Insert dummy client & product
        client_id = conn.execute(
            "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("BENCHMARK_CLIENT", "0000", "ADDR", "BENCHMARK_TEST", 0.0)
        ).fetchone()[0]

        product_id = conn.execute(
            "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("BENCHMARK_PRODUCT", "kg", 10000.0, 100.0, 50.0)
        ).fetchone()[0]

        print(f"Benchmark setup: client_id={client_id}, product_id={product_id}")

        # Insert 5000 sales rows inside a transaction
        print("Inserting 5000 sales records to simulate database load...")
        start_insert = time.perf_counter()
        for idx in range(5000):
            # Alternate sale_type and sale_date
            sale_type = "credit" if idx % 2 == 0 else "cash"
            sale_date = f"2026-05-{1 + (idx % 28):02d}"
            conn.execute(
                """
                INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (client_id, product_id, 10.0, "kg", 100.0, 1000.0, sale_type, 500.0, 500.0, 50.0, 500.0, sale_date, "BENCHMARK_TEST")
            )
        conn.commit()
        end_insert = time.perf_counter()
        print(f"Inserted 5000 records in {end_insert - start_insert:.4f} seconds.")

        # Let's benchmark the query that retrieves client sales sorted by date
        test_query = "SELECT * FROM sales WHERE client_id = %s AND sale_type = 'credit' ORDER BY sale_date DESC"
        
        # Test 1: Query WITH indexes
        print("\n--- Test 1: Query WITH index `idx_sales_client_date_type` ---")
        times_with_index = []
        for _ in range(50):
            t0 = time.perf_counter()
            cur = conn.execute(test_query, (client_id,))
            cur.fetchall()
            cur.close()
            times_with_index.append(time.perf_counter() - t0)
        avg_with_index = sum(times_with_index) / len(times_with_index)
        print(f"Average query execution time: {avg_with_index * 1000:.4f} ms")

        # Test 2: Drop the index and query WITHOUT it
        print("\nDropping index `idx_sales_client_date_type`...")
        conn.execute("DROP INDEX IF EXISTS idx_sales_client_date_type")
        conn.commit()

        print("\n--- Test 2: Query WITHOUT index `idx_sales_client_date_type` ---")
        times_without_index = []
        for _ in range(50):
            t0 = time.perf_counter()
            cur = conn.execute(test_query, (client_id,))
            cur.fetchall()
            cur.close()
            times_without_index.append(time.perf_counter() - t0)
        avg_without_index = sum(times_without_index) / len(times_without_index)
        print(f"Average query execution time: {avg_without_index * 1000:.4f} ms")

        # Performance summary
        speedup = (avg_without_index - avg_with_index) / avg_without_index * 100
        print(f"\nSpeedup with composite index: {speedup:.2f}% (from {avg_without_index * 1000:.2f}ms to {avg_with_index * 1000:.2f}ms)")

        # Re-create the index to leave the database clean
        print("\nRe-creating index `idx_sales_client_date_type`...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_client_date_type ON sales(client_id, sale_date, sale_type)")
        conn.commit()

    finally:
        # Clean up test records
        print("\nCleaning up benchmark test records from database...")
        conn.execute("DELETE FROM sales WHERE notes = 'BENCHMARK_TEST'")
        conn.execute("DELETE FROM finished_products WHERE name = 'BENCHMARK_PRODUCT'")
        conn.execute("DELETE FROM clients WHERE name = 'BENCHMARK_CLIENT'")
        conn.commit()
        conn.close()
        print("Benchmark session complete.")

if __name__ == "__main__":
    run_benchmark()
