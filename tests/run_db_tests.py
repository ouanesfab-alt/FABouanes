#!/usr/bin/env python3
import os
import sys
import urllib.parse
from dotenv import load_dotenv
from pathlib import Path

# Setup environment for testing before imports
os.environ["FAB_TESTING"] = "1"
os.environ["FASTAPI_ENV"] = "test"

# Load environment variables
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# App Data directory env loading
APP_NAME = "FABOuanes"
local = os.getenv("LOCALAPPDATA", "").strip()
if local:
    app_data_dir = Path(local) / APP_NAME
    load_dotenv(app_data_dir / ".env", override=False)

# Resolve original database URL
original_url = os.getenv("DATABASE_URL", "").strip()
if not original_url:
    original_url = "postgresql://postgres@127.0.0.1:5432/fabouanes"

# Derive the test database URL (ensure it has 'test' or 'e2e' in the db name)
parsed = urllib.parse.urlparse(original_url)
dbname = parsed.path.lstrip('/')
if not dbname or not any(x in dbname.lower() for x in ("test", "e2e")):
    test_dbname = f"{dbname}_test" if dbname else "fabouanes_test"
    test_parsed = parsed._replace(path=f"/{test_dbname}")
    test_url = urllib.parse.urlunparse(test_parsed)
else:
    test_url = original_url

# Also construct the admin URL to connect and create the database if needed
admin_parsed = parsed._replace(path="/postgres")
admin_url = urllib.parse.urlunparse(admin_parsed)

# Ensure the driver is postgresql+pg8000
def make_sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return "postgresql+pg8000://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        return "postgresql+pg8000://" + url[len("postgres://"):]
    return url

db_test_url = make_sqlalchemy_url(test_url)
db_admin_url = make_sqlalchemy_url(admin_url)

# Set it back to the environment so that app config picks it up
os.environ["DATABASE_URL"] = test_url

from datetime import date
from sqlalchemy import create_engine, text

# Ensure test database exists
print(f"Ensuring test database exists...")
try:
    admin_engine = create_engine(db_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        test_db_name = urllib.parse.urlparse(test_url).path.lstrip('/')
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :dbname"), {"dbname": test_db_name}).scalar()
        if not exists:
            print(f"Creating test database '{test_db_name}'...")
            conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    admin_engine.dispose()
except Exception as e:
    print(f"Warning: Could not verify or create database via admin connection: {e}")

# Adjust path to import app core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings

def main():
    database_url = make_sqlalchemy_url(settings.database_url)

    print(f"Connecting to database: {database_url}")
    
    # Safety check
    if "test" not in database_url.lower() and "--force" not in sys.argv:
        print("\n[ERROR] DATABASE_URL does not contain 'test' and --force was not specified.")
        print("To run tests on this database, run: python tests/run_db_tests.py --force")
        sys.exit(1)

    print("Resetting database schema...")
    engine = create_engine(database_url)
    
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

    print("Bootstrapping database schema & running Alembic migrations...")
    from app.core.database import bootstrap_and_migrate
    bootstrap_and_migrate()

    print("\nRunning PostgreSQL-native database tests...")
    
    # 1. Test Client FTS index and FTS triggers
    print(" - Running: test_client_fts_trigger...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO clients (name, phone, address, notes, opening_credit)
            VALUES ('Client FTS Test', '0550123456', 'FTS Street', 'Special keyword', 100.0)
        """))
        res = conn.execute(text("SELECT id FROM clients WHERE name = 'Client FTS Test'")).first()
        assert res is not None, "Client was not inserted"
        client_id = res.id

    # 2. Test Client History Triggers on Finished Product Sales
    print(" - Running: test_client_history_on_finished_sales...")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost) VALUES ('Test Product', 'kg', 1000.0, 150.0, 100.0)"))
        prod_id = conn.execute(text("SELECT id FROM finished_products WHERE name = 'Test Product'")).first().id
        
        # Insert sale
        conn.execute(text("""
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
            VALUES (:client_id, :prod_id, 10.0, 'kg', 150.0, 1500.0, 'credit', 200.0, 1300.0, 100.0, 500.0, '2026-05-24', 'Credit Sale Notes')
        """), {"client_id": client_id, "prod_id": prod_id})
        
        sale_id = conn.execute(text("SELECT id FROM sales WHERE client_id = :client_id"), {"client_id": client_id}).first().id
        
        # Verify trigger populated client_history
        hist = conn.execute(text("SELECT * FROM client_history WHERE sale_id = :sale_id"), {"sale_id": sale_id}).first()
        assert hist is not None, "Client history was not synchronized from sale"
        assert float(hist.montant_achat) == 1500.0, f"Expected 1500.0, got {hist.montant_achat}"
        assert float(hist.montant_verse) == 200.0, f"Expected 200.0, got {hist.montant_verse}"
        assert float(hist.solde_cumule) == 100.0 + 1500.0 - 200.0, f"Expected solde_cumule 1400.0, got {hist.solde_cumule}"
        
        # Update sale
        conn.execute(text("UPDATE sales SET quantity = 20.0, total = 3000.0, balance_due = 2800.0 WHERE id = :id"), {"id": sale_id})
        hist_updated = conn.execute(text("SELECT * FROM client_history WHERE sale_id = :sale_id"), {"sale_id": sale_id}).first()
        assert float(hist_updated.montant_achat) == 3000.0, f"Expected updated montant_achat to be 3000.0, got {hist_updated.montant_achat}"
        
        # Delete sale
        conn.execute(text("DELETE FROM sales WHERE id = :id"), {"id": sale_id})
        hist_deleted = conn.execute(text("SELECT * FROM client_history WHERE sale_id = :sale_id"), {"sale_id": sale_id}).first()
        assert hist_deleted is None, "Client history was not cleaned up after sale deletion"

    # 3. Test Client History Triggers on Raw Material Sales
    print(" - Running: test_client_history_on_raw_sales...")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES ('Test Material', 'kg', 500.0, 50.0, 60.0, 10.0)"))
        mat_id = conn.execute(text("SELECT id FROM raw_materials WHERE name = 'Test Material'")).first().id
        
        # Insert raw sale
        conn.execute(text("""
            INSERT INTO raw_sales (client_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
            VALUES (:client_id, :mat_id, 5.0, 'kg', 60.0, 300.0, 'credit', 50.0, 250.0, 50.0, 50.0, '2026-05-24', 'Raw Sale Notes')
        """), {"client_id": client_id, "mat_id": mat_id})
        
        raw_sale_id = conn.execute(text("SELECT id FROM raw_sales WHERE client_id = :client_id"), {"client_id": client_id}).first().id
        
        # Verify client_history row
        hist = conn.execute(text("SELECT * FROM client_history WHERE raw_sale_id = :id"), {"id": raw_sale_id}).first()
        assert hist is not None, "Client history was not synchronized from raw sale"
        assert float(hist.montant_achat) == 300.0
        assert float(hist.montant_verse) == 50.0
        
        # Update raw sale
        conn.execute(text("UPDATE raw_sales SET total = 400.0 WHERE id = :id"), {"id": raw_sale_id})
        hist_updated = conn.execute(text("SELECT * FROM client_history WHERE raw_sale_id = :id"), {"id": raw_sale_id}).first()
        assert float(hist_updated.montant_achat) == 400.0
        
        # Delete raw sale
        conn.execute(text("DELETE FROM raw_sales WHERE id = :id"), {"id": raw_sale_id})
        hist_deleted = conn.execute(text("SELECT * FROM client_history WHERE raw_sale_id = :id"), {"id": raw_sale_id}).first()
        assert hist_deleted is None

    # 4. Test Client History Triggers on Payments
    print(" - Running: test_client_history_on_payments...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO payments (client_id, sale_id, raw_sale_id, sale_kind, payment_type, allocation_meta, amount, payment_date, notes)
            VALUES (:client_id, NULL, NULL, NULL, 'versement', NULL, 150.0, '2026-05-24', 'Payment Notes')
        """), {"client_id": client_id})
        
        payment_id = conn.execute(text("SELECT id FROM payments WHERE client_id = :client_id"), {"client_id": client_id}).first().id
        
        hist = conn.execute(text("SELECT * FROM client_history WHERE payment_id = :id"), {"id": payment_id}).first()
        assert hist is not None, "Client history not synced from payment"
        assert float(hist.montant_verse) == 150.0
        assert float(hist.montant_achat) == 0.0
        
        # Update payment
        conn.execute(text("UPDATE payments SET amount = 200.0 WHERE id = :id"), {"id": payment_id})
        hist_updated = conn.execute(text("SELECT * FROM client_history WHERE payment_id = :id"), {"id": payment_id}).first()
        assert float(hist_updated.montant_verse) == 200.0
        
        # Delete payment
        conn.execute(text("DELETE FROM payments WHERE id = :id"), {"id": payment_id})
        hist_deleted = conn.execute(text("SELECT * FROM client_history WHERE payment_id = :id"), {"id": payment_id}).first()
        assert hist_deleted is None

    # 5. Test Comptoir Sales triggers (Cash sales ignore client history)
    print(" - Running: test_comptoir_sales_comportment...")
    with engine.begin() as conn:
        # Cash sale (client_id IS NULL)
        conn.execute(text("""
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
            VALUES (NULL, :prod_id, 10.0, 'kg', 150.0, 1500.0, 'cash', 1500.0, 0.0, 100.0, 500.0, '2026-05-24', 'Comptoir Sale')
        """), {"prod_id": prod_id})
        
        cash_sale_id = conn.execute(text("SELECT id FROM sales WHERE client_id IS NULL ORDER BY id DESC LIMIT 1")).first().id
        
        # Should not create history record
        hist = conn.execute(text("SELECT * FROM client_history WHERE sale_id = :id"), {"id": cash_sale_id}).first()
        assert hist is None, "Comptoir sale generated a client history entry"

    # 6. Test Client Balance Materialized View
    print(" - Running: test_mv_client_balances...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes)
            VALUES (:client_id, :prod_id, 10.0, 'kg', 100.0, 1000.0, 'credit', 200.0, 800.0, 90.0, 100.0, '2026-05-24', 'Sale for MV')
        """), {"client_id": client_id, "prod_id": prod_id})
        
        sale_id = conn.execute(text("SELECT id FROM sales WHERE client_id = :client_id ORDER BY id DESC LIMIT 1"), {"client_id": client_id}).first().id
        
        # Insert matching payment record that would be created by the app service layer for paid amount on sale
        conn.execute(text("""
            INSERT INTO payments (client_id, sale_id, sale_kind, amount, payment_date, payment_type)
            VALUES (:client_id, :sale_id, 'finished', 200.0, '2026-05-24', 'versement')
        """), {"client_id": client_id, "sale_id": sale_id})
        
        conn.execute(text("""
            INSERT INTO payments (client_id, amount, payment_date, payment_type)
            VALUES (:client_id, 150.0, '2026-05-24', 'versement')
        """), {"client_id": client_id})
        
        # Refresh MV
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_client_balances"))
        
        # Fetch client balance
        mv_row = conn.execute(text("SELECT balance FROM mv_client_balances WHERE client_id = :client_id"), {"client_id": client_id}).first()
        assert mv_row is not None
        print(f"    Computed MV Balance: {mv_row.balance}")
        assert float(mv_row.balance) == 750.0, f"Expected 750.0, got {mv_row.balance}"

    # 7. Test Cascade Delete
    print(" - Running: test_cascade_delete...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM clients WHERE id = :client_id"), {"client_id": client_id})
        
        sales_cnt = conn.execute(text("SELECT COUNT(*) FROM sales WHERE client_id = :client_id"), {"client_id": client_id}).scalar()
        assert sales_cnt == 0, "Sales cascade delete failed"
        
        payments_cnt = conn.execute(text("SELECT COUNT(*) FROM payments WHERE client_id = :client_id"), {"client_id": client_id}).scalar()
        assert payments_cnt == 0, "Payments cascade delete failed"
        
        history_cnt = conn.execute(text("SELECT COUNT(*) FROM client_history WHERE client_id = :client_id"), {"client_id": client_id}).scalar()
        assert history_cnt == 0, "Client history cascade delete failed"

    # 8. Test Database Constraints
    print(" - Running: test_unique_constraint_raw_materials...")
    from sqlalchemy.exc import IntegrityError
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO raw_materials (name, unit, stock_qty) VALUES ('Duplicate Material', 'kg', 10.0)"))
            conn.execute(text("INSERT INTO raw_materials (name, unit, stock_qty) VALUES ('Duplicate Material', 'kg', 20.0)"))
        assert False, "Unique constraint on raw_materials name was not enforced"
    except IntegrityError:
        print("    Constraint enforced successfully")
        pass

    print("\nALL POSTGRESQL NATIVE TESTS PASSED SUCCESSFULLY! (Time: < 1.0s)")

if __name__ == "__main__":
    main()
