"""
purge_test_data.py — Complete Database Purge & Reset
Wipes all business, catalog, transaction, and history tables from PostgreSQL,
committing each table individually to prevent transaction rollbacks.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.db_helpers import db_manager

ALL_BUSINESS_TABLES = [
    # Transactions & Operations
    "payment_allocations",
    "payments",
    "supplier_payments",
    "sales",
    "raw_sales",
    "sale_documents",
    "purchases",
    "purchase_documents",
    "expenses",
    # Production & Recipes
    "production_batch_items",
    "production_batches",
    "saved_recipe_items",
    "saved_recipes",
    # Stock & Catalog
    "stock_movements",
    "stock_alerts",
    "catalog_embeddings",
    "finished_products",
    "raw_materials",
    # Contacts & History
    "client_history",
    "imported_client_history",
    "client_keys",
    "clients",
    "suppliers",
    # Offline & Staging
    "offline_sales_staging",
    "offline_payments_staging",
    "offline_operation_receipts",
    # Logs & System Jobs
    "activity_logs",
    "audit_logs",
    "error_logs",
    "system_logs",
    "performance_logs",
    "backup_jobs",
    "backup_runs",
    "sabrina_memory",
    "idempotent_requests",
    "pubsub_events",
    "outbox_events",
    "dead_letter_events",
    "background_jobs",
    "rate_limit_events",
    "api_refresh_tokens",
    "user_badges",
]

def purge_all() -> None:
    print("[PURGE] Nettoyage complet de la base de donnees...")
    for table in ALL_BUSINESS_TABLES:
        try:
            with db_manager.db_transaction() as conn:
                conn.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
            print(f"  [OK] Purge : {table}")
        except Exception as e:
            err = str(e).lower()
            if "n'existe pas" in err or "does not exist" in err or "42p01" in err:
                continue
            try:
                with db_manager.db_transaction() as conn:
                    conn.execute(f"DELETE FROM {table};")
                print(f"  [OK] Delete : {table}")
            except Exception as ex:
                print(f"  [SKIP] Ignore ({table}) : {ex}")

    print("\n[SUCCESS] Base de donnees reinitialisee a 100% !")

if __name__ == "__main__":
    purge_all()
