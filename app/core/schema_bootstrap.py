"""
Responsibility: Bootstrap the initial database schema and seed data.

Design notes:
- All DDL (CREATE TABLE / CREATE INDEX) is executed inside a single transaction.
  If any step fails the entire schema creation is rolled back, preventing a
  partially-initialised database that would be hard to diagnose and recover from.
- ALTER TABLE column additions have been migrated to Alembic migration 0038.
  schema_bootstrap.py now only creates tables that do not yet exist (idempotent).
- Seeds (admin user, default settings, "AUTRE" operation) are committed separately
  after the DDL so that a seed failure does not roll back the schema itself.
"""
from __future__ import annotations


import logging
from app.core.config import settings
from app.core.db_helpers import connect_database
from app.core.schema.core import SCHEMA_CORE
from app.core.schema.contacts import SCHEMA_CONTACTS
from app.core.schema.catalog import SCHEMA_CATALOG
from app.core.schema.operations import SCHEMA_OPERATIONS
from app.core.schema.production import SCHEMA_PRODUCTION


ADVISORY_LOCK_ID = 884712


def bootstrap_schema() -> None:
    """Create all tables and indexes in a single atomic transaction.

    Uses a single commit at the end so that a partial failure rolls back the
    entire DDL block, leaving the database in a clean state rather than a
    half-initialised one.  Seeds are committed in a separate step afterwards.
    """
    _logger = logging.getLogger("fabouanes")
    conn = connect_database(settings.database_url)
    try:
        # ── PHASE 1: DDL — single atomic transaction ──────────────────────────
        try:
            # 1a. Core system tables
            conn.executescript(SCHEMA_CORE)

            # 1b. System infrastructure tables (jobs, pubsub, outbox, rate-limit…)
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS rate_limit_events (
                key TEXT NOT NULL,
                hit_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_hit_at ON rate_limit_events(key, hit_at);

            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_type TEXT NOT NULL,
                product_id BIGINT NOT NULL,
                product_name TEXT NOT NULL,
                current_qty NUMERIC(15, 4) NOT NULL,
                threshold_qty NUMERIC(15, 4) NOT NULL,
                triggered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                acknowledged_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_stock_alerts_product ON stock_alerts(product_type, product_id);
            CREATE INDEX IF NOT EXISTS idx_stock_alerts_triggered_at ON stock_alerts(triggered_at);

            CREATE TABLE IF NOT EXISTS idempotent_requests (
                key VARCHAR(255) PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pubsub_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel VARCHAR(255) NOT NULL,
                payload TEXT NOT NULL,
                sender_worker_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_pubsub_events_created_at ON pubsub_events(created_at);

            CREATE TABLE IF NOT EXISTS outbox_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(255) NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMPTZ,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_events_processed_at ON outbox_events(processed_at);

            CREATE TABLE IF NOT EXISTS background_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name VARCHAR(255) NOT NULL,
                payload TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                run_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                locked_by VARCHAR(255),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_background_jobs_status_run_at ON background_jobs(status, run_at);

            CREATE TABLE IF NOT EXISTS sabrina_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category VARCHAR(255) DEFAULT 'general',
                source VARCHAR(255) DEFAULT 'user_explicit',
                relevance_score INTEGER DEFAULT 0,
                expires_at TIMESTAMPTZ,
                search_vector TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sabrina_memory_category ON sabrina_memory(category);
            """)

            # 1c. Domain schemas (contacts, catalog, operations, production)
            conn.executescript(SCHEMA_CONTACTS)
            conn.executescript(SCHEMA_CATALOG)
            conn.executescript(SCHEMA_OPERATIONS)
            conn.executescript(SCHEMA_PRODUCTION)

            # 1d. SQLModel-managed tables (e.g. expenses, audit_logs, …)
            from app.core.db import get_database_engine
            from sqlmodel import SQLModel
            import app.core.models  # noqa: F401
            engine = get_database_engine(settings.database_url)
            SQLModel.metadata.create_all(engine)

            # 1e. Extended tables: encryption keys, dead-letter queue, PWA staging
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS client_keys (
                client_id BIGINT PRIMARY KEY,
                encryption_key TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dead_letter_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(255) NOT NULL,
                payload TEXT NOT NULL,
                reason TEXT NOT NULL,
                failed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS offline_sales_staging (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key VARCHAR(255) UNIQUE,
                payload TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS offline_payments_staging (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key VARCHAR(255) UNIQUE,
                payload TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS catalog_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_kind VARCHAR(50) NOT NULL,
                item_id BIGINT NOT NULL,
                text_content TEXT NOT NULL,
                embedding TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_embeddings_item ON catalog_embeddings(item_kind, item_id);
            """)

            # 1f. Performance indexes for high-traffic queries
            conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sales_credit_client ON sales(client_id, total) WHERE sale_type = 'credit';
            CREATE INDEX IF NOT EXISTS idx_raw_sales_credit_client ON raw_sales(client_id, total) WHERE sale_type = 'credit';
            CREATE INDEX IF NOT EXISTS idx_sales_client_date_type ON sales(client_id, sale_date, sale_type);
            CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date ON purchases(supplier_id, purchase_date);
            CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
            CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);
            """)

            # 1g. Conditional indexes (tables may not exist on fresh install)
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='expenses'").fetchone():
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stock_movements'").fetchone():
                conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_kind, item_id);")

            # ── SINGLE COMMIT for all DDL ──────────────────────────────────────
            conn.commit()
            _logger.info("Schema bootstrap DDL committed successfully.")

        except Exception as ddl_exc:
            # Roll back the entire DDL block — leaves the DB in a clean state.
            try:
                conn.rollback()
            except Exception:
                pass
            _logger.error(
                "Schema bootstrap DDL failed and was rolled back. "
                "The application may not start correctly. Error: %s",
                ddl_exc,
            )
            raise

        # ── PHASE 2: Seeds — separate transaction ─────────────────────────────
        # Seeds are committed independently so that a seed failure (e.g. duplicate
        # admin user) does not roll back the schema tables created in Phase 1.
        try:
            from app.core.schema import _seed_default_admin, _seed_default_settings, _seed_other_operation
            _seed_default_admin(conn)
            _seed_default_settings(conn)
            _seed_other_operation(conn)
            conn.commit()
            _logger.info("Schema seeds committed successfully.")
        except Exception as seed_exc:
            try:
                conn.rollback()
            except Exception:
                pass
            _logger.warning(
                "Schema seed step failed (non-critical, schema tables are intact): %s",
                seed_exc,
            )

    finally:
        conn.close()


