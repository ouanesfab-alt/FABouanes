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


def _adapt_schema_sql(sql: str) -> str:
    """
    Adapt schema SQL from PostgreSQL to target database (SQLite, etc).
    """
    if not settings.database_url.startswith("sqlite"):
        return sql
    
    # Process the schema for SQLite
    sql = re.sub(r'\bBIGSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql)
    sql = re.sub(r'\bBIGSERIAL\b', 'INTEGER', sql)
    sql = re.sub(r'\bDOUBLE\s+PRECISION\b', 'REAL', sql)
    sql = sql.replace('::text', '')
    sql = sql.replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
    
    return sql


def bootstrap_schema() -> None:
    conn = connect_database(settings.database_url)
    try:
        # Core schema first
        conn.executescript(_adapt_schema_sql(SCHEMA_CORE))
        
        # Then domain schemas
        conn.executescript(_adapt_schema_sql(SCHEMA_CONTACTS))
        conn.executescript(_adapt_schema_sql(SCHEMA_CATALOG))
        conn.executescript(_adapt_schema_sql(SCHEMA_OPERATIONS))
        conn.executescript(_adapt_schema_sql(SCHEMA_PRODUCTION))
        
        # Auto-migrate existing database for operations time tracking
        from app.core.db import list_columns
        for table in ["purchases", "sales", "raw_sales", "payments"]:
            try:
                cols = list_columns(conn, table)
                if cols and "created_at" not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()
