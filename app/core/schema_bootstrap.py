"""
Responsibility: Bootstrap the initial database schema and seed data.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.db import connect_database
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
        """)
        
        # Then domain schemas
        conn.executescript(SCHEMA_CONTACTS)
        conn.executescript(SCHEMA_CATALOG)
        conn.executescript(SCHEMA_OPERATIONS)
        conn.executescript(SCHEMA_PRODUCTION)
        
        # Then discover and execute module schemas
        try:
            from pathlib import Path
            from app.core.registry import discover_modules, get_enabled_modules
            discover_modules(settings.base_dir / "app" / "modules")
            for module in get_enabled_modules():
                for sql in module.schema_sql:
                    conn.executescript(sql)
        except Exception as e:
            import logging
            logging.getLogger("fabouanes").warning("Failed to bootstrap module schemas: %s", e)
        
        # Auto-migrate existing database for operations time tracking and finished product purchases
        from app.core.db import list_columns
        for table in ["purchases", "sales", "raw_sales", "payments"]:
            try:
                cols = list_columns(conn, table)
                if cols and "created_at" not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                pass

        try:
            cols = list_columns(conn, "purchases")
            if cols and "finished_product_id" not in cols:
                conn.execute("ALTER TABLE purchases ADD COLUMN finished_product_id BIGINT REFERENCES finished_products(id) ON DELETE CASCADE")
            if cols:
                # PostgreSQL command to drop not null constraint if present
                conn.execute("ALTER TABLE purchases ALTER COLUMN raw_material_id DROP NOT NULL")
        except Exception:
            pass

        conn.commit()
    finally:
        conn.close()
