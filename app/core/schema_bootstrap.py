"""
Responsibility: Bootstrap the initial database schema and seed data.
"""
from __future__ import annotations


from app.core.config import settings
from app.core.db_helpers import connect_database
from app.core.schema.core import SCHEMA_CORE
from app.core.schema.contacts import SCHEMA_CONTACTS
from app.core.schema.catalog import SCHEMA_CATALOG
from app.core.schema.operations import SCHEMA_OPERATIONS
from app.core.schema.production import SCHEMA_PRODUCTION





def bootstrap_schema() -> None:
    conn = connect_database(settings.database_url)
    try:
        # Core schema first
        conn.executescript(SCHEMA_CORE)

        # Create rate_limit_events and stock_alerts tables
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            key TEXT NOT NULL,
            hit_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_hit_at ON rate_limit_events(key, hit_at);

        CREATE TABLE IF NOT EXISTS stock_alerts (
            id BIGSERIAL PRIMARY KEY,
            product_type TEXT NOT NULL,
            product_id BIGINT NOT NULL,
            product_name TEXT NOT NULL,
            current_qty NUMERIC(15, 4) NOT NULL,
            threshold_qty NUMERIC(15, 4) NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
            id BIGSERIAL PRIMARY KEY,
            channel VARCHAR(255) NOT NULL,
            payload TEXT NOT NULL,
            sender_worker_id VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pubsub_events_created_at ON pubsub_events(created_at);

        CREATE TABLE IF NOT EXISTS outbox_events (
            id BIGSERIAL PRIMARY KEY,
            event_type VARCHAR(255) NOT NULL,
            payload TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMPTZ,
            retry_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_outbox_events_processed_at ON outbox_events(processed_at);

        CREATE TABLE IF NOT EXISTS background_jobs (
            id BIGSERIAL PRIMARY KEY,
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
        """)

        # Then domain schemas
        conn.executescript(SCHEMA_CONTACTS)
        conn.executescript(SCHEMA_CATALOG)
        conn.executescript(SCHEMA_OPERATIONS)
        conn.executescript(SCHEMA_PRODUCTION)

        # Then schema updates and indexes for Options J, I, K
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS client_keys (
            client_id BIGINT PRIMARY KEY,
            encryption_key TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dead_letter_events (
            id BIGSERIAL PRIMARY KEY,
            event_type VARCHAR(255) NOT NULL,
            payload TEXT NOT NULL,
            reason TEXT NOT NULL,
            failed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_sales_credit_client ON sales(client_id, total) WHERE sale_type = 'credit';
        CREATE INDEX IF NOT EXISTS idx_raw_sales_credit_client ON raw_sales(client_id, total) WHERE sale_type = 'credit';

        -- Option N: Composite and Search Indexes for SQL Query Optimization
        CREATE INDEX IF NOT EXISTS idx_sales_client_date_type ON sales(client_id, sale_date, sale_type);
        CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date ON purchases(supplier_id, purchase_date);
        CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
        CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);

        -- Additional Missing Foreign Key & Search Indexes
        CREATE INDEX IF NOT EXISTS idx_purchases_finished_product_id ON purchases(finished_product_id);
        CREATE INDEX IF NOT EXISTS idx_prod_items_material_id ON production_batch_items(raw_material_id);
        CREATE INDEX IF NOT EXISTS idx_saved_recipe_items_material_id ON saved_recipe_items(raw_material_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);
        CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_performance_logs_created_at ON performance_logs(created_at);
        """)

        # Then discover and execute module schemas
        try:
            from app.core.registry import discover_modules, get_enabled_modules
            discover_modules(settings.base_dir / "app" / "modules")
            for module in get_enabled_modules():
                for sql in module.schema_sql:
                    conn.executescript(sql)
        except Exception as e:
            import logging
            logging.getLogger("fabouanes").warning("Failed to bootstrap module schemas: %s", e)

        # Auto-migrate existing database for operations time tracking and finished product purchases
        from app.core.db_helpers import list_columns
        try:
            cols = list_columns(conn, "users")
            if cols and "custom_permissions_json" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN custom_permissions_json TEXT DEFAULT '[]'")
        except Exception:
            import logging
            logging.getLogger("fabouanes").debug("Auto-migration for users.custom_permissions_json skipped", exc_info=True)

        for table in ["purchases", "sales", "raw_sales", "payments"]:
            try:
                cols = list_columns(conn, table)
                if cols and "created_at" not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                logging.getLogger("fabouanes").debug("Auto-migration column add skipped for %s", table, exc_info=True)

        try:
            cols = list_columns(conn, "purchases")
            if cols and "finished_product_id" not in cols:
                conn.execute("ALTER TABLE purchases ADD COLUMN finished_product_id BIGINT REFERENCES finished_products(id) ON DELETE CASCADE")
            if cols:
                # PostgreSQL command to drop not null constraint if present
                conn.execute("ALTER TABLE purchases ALTER COLUMN raw_material_id DROP NOT NULL")
        except Exception:
            logging.getLogger("fabouanes").debug("Auto-migration for purchases.finished_product_id skipped", exc_info=True)

        try:
            cols = list_columns(conn, "outbox_events")
            if cols:
                if "retry_count" not in cols:
                    conn.execute("ALTER TABLE outbox_events ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
                if "last_error" not in cols:
                    conn.execute("ALTER TABLE outbox_events ADD COLUMN last_error TEXT")
        except Exception:
            logging.getLogger("fabouanes").debug("Auto-migration for outbox_events retry columns skipped", exc_info=True)

        conn.commit()

        # ── Seeds (absorbé depuis schema.py) ─────────────────────────────────
        from app.core.schema import _seed_default_admin, _seed_default_settings, _seed_other_operation
        _seed_default_admin(conn)
        _seed_default_settings(conn)
        _seed_other_operation(conn)
        conn.commit()
    finally:
        conn.close()
