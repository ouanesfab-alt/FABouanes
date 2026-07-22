"""Consolidate manual ALTER TABLE migrations from schema_bootstrap.py

All the ad-hoc ALTER TABLE ADD COLUMN statements that were scattered in
schema_bootstrap.py are now managed by Alembic as a single versioned,
reversible migration (P2.1 improvement).

Revision ID: 0038_consolidate_schema_bootstrap_alters
Revises: 0037_missing_indexes_phase3
Create Date: 2026-07-22 17:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0038_consolidate_schema_bootstrap_alters"
down_revision = "0037_missing_indexes_phase3"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    """Check whether a column exists in the given table (SQLite-safe)."""
    try:
        result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        rows = result.fetchall()
        return any(row[1] == column for row in rows)
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    """Check whether a table exists (SQLite-safe)."""
    try:
        result = conn.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        )
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # ── users ──────────────────────────────────────────────────────────────────
    if _table_exists(conn, "users"):
        if not _has_column(conn, "users", "custom_permissions_json"):
            op.execute(sa.text("ALTER TABLE users ADD COLUMN custom_permissions_json TEXT DEFAULT '[]'"))
        if not _has_column(conn, "users", "xp"):
            op.execute(sa.text("ALTER TABLE users ADD COLUMN xp INTEGER NOT NULL DEFAULT 0"))
        if not _has_column(conn, "users", "level"):
            op.execute(sa.text("ALTER TABLE users ADD COLUMN level INTEGER NOT NULL DEFAULT 1"))

    # ── clients ────────────────────────────────────────────────────────────────
    if _table_exists(conn, "clients"):
        if not _has_column(conn, "clients", "search_vector"):
            op.execute(sa.text("ALTER TABLE clients ADD COLUMN search_vector TEXT"))
        if not _has_column(conn, "clients", "updated_at"):
            op.execute(sa.text("ALTER TABLE clients ADD COLUMN updated_at TIMESTAMP"))

    # ── purchases ──────────────────────────────────────────────────────────────
    if _table_exists(conn, "purchases"):
        if not _has_column(conn, "purchases", "finished_product_id"):
            op.execute(sa.text(
                "ALTER TABLE purchases ADD COLUMN finished_product_id BIGINT "
                "REFERENCES finished_products(id) ON DELETE CASCADE"
            ))
        if not _has_column(conn, "purchases", "custom_item_name"):
            op.execute(sa.text("ALTER TABLE purchases ADD COLUMN custom_item_name TEXT"))
        if not _has_column(conn, "purchases", "created_at"):
            op.execute(sa.text("ALTER TABLE purchases ADD COLUMN created_at TIMESTAMP"))
        if not _has_column(conn, "purchases", "updated_at"):
            op.execute(sa.text("ALTER TABLE purchases ADD COLUMN updated_at TIMESTAMP"))

    # ── finished_products ──────────────────────────────────────────────────────
    if _table_exists(conn, "finished_products"):
        if not _has_column(conn, "finished_products", "alert_threshold"):
            op.execute(sa.text("ALTER TABLE finished_products ADD COLUMN alert_threshold NUMERIC DEFAULT 0"))
        if not _has_column(conn, "finished_products", "updated_at"):
            op.execute(sa.text("ALTER TABLE finished_products ADD COLUMN updated_at TIMESTAMP"))

    # ── raw_materials ──────────────────────────────────────────────────────────
    if _table_exists(conn, "raw_materials"):
        if not _has_column(conn, "raw_materials", "alert_threshold"):
            op.execute(sa.text("ALTER TABLE raw_materials ADD COLUMN alert_threshold NUMERIC DEFAULT 0"))
        if not _has_column(conn, "raw_materials", "updated_at"):
            op.execute(sa.text("ALTER TABLE raw_materials ADD COLUMN updated_at TIMESTAMP"))

    # ── raw_sales ──────────────────────────────────────────────────────────────
    if _table_exists(conn, "raw_sales"):
        if not _has_column(conn, "raw_sales", "custom_item_name"):
            op.execute(sa.text("ALTER TABLE raw_sales ADD COLUMN custom_item_name TEXT"))
        if not _has_column(conn, "raw_sales", "created_at"):
            op.execute(sa.text("ALTER TABLE raw_sales ADD COLUMN created_at TIMESTAMP"))
        if not _has_column(conn, "raw_sales", "updated_at"):
            op.execute(sa.text("ALTER TABLE raw_sales ADD COLUMN updated_at TIMESTAMP"))

    # ── tables needing created_at / updated_at ────────────────────────────────
    for tbl in ("sales", "payments", "purchase_documents", "sale_documents"):
        if _table_exists(conn, tbl):
            if not _has_column(conn, tbl, "created_at"):
                op.execute(sa.text(f"ALTER TABLE {tbl} ADD COLUMN created_at TIMESTAMP"))
            if not _has_column(conn, tbl, "updated_at"):
                op.execute(sa.text(f"ALTER TABLE {tbl} ADD COLUMN updated_at TIMESTAMP"))

    # ── doc_number columns ────────────────────────────────────────────────────
    if _table_exists(conn, "purchase_documents") and not _has_column(conn, "purchase_documents", "doc_number"):
        op.execute(sa.text("ALTER TABLE purchase_documents ADD COLUMN doc_number TEXT"))
    if _table_exists(conn, "sale_documents") and not _has_column(conn, "sale_documents", "doc_number"):
        op.execute(sa.text("ALTER TABLE sale_documents ADD COLUMN doc_number TEXT"))

    # ── activity_logs ──────────────────────────────────────────────────────────
    if _table_exists(conn, "activity_logs"):
        for col_def, col_name in [
            ("user_id BIGINT", "user_id"),
            ("old_value TEXT", "old_value"),
            ("new_value TEXT", "new_value"),
            ("ip_address TEXT", "ip_address"),
        ]:
            if not _has_column(conn, "activity_logs", col_name):
                op.execute(sa.text(f"ALTER TABLE activity_logs ADD COLUMN {col_def}"))

    # ── updated_at for contact/supplier/catalog tables ────────────────────────
    for tbl in ("contacts", "suppliers", "catalog_items"):
        if _table_exists(conn, tbl) and not _has_column(conn, tbl, "updated_at"):
            op.execute(sa.text(f"ALTER TABLE {tbl} ADD COLUMN updated_at TIMESTAMP"))

    # ── outbox_events retry columns ────────────────────────────────────────────
    if _table_exists(conn, "outbox_events"):
        if not _has_column(conn, "outbox_events", "retry_count"):
            op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"))
        if not _has_column(conn, "outbox_events", "last_error"):
            op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN last_error TEXT"))

    # ── new tables (Option J / I / K) ─────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS client_keys (
            client_id BIGINT PRIMARY KEY,
            encryption_key TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS dead_letter_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type VARCHAR(255) NOT NULL,
            payload TEXT NOT NULL,
            reason TEXT NOT NULL,
            failed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS offline_sales_staging (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key VARCHAR(255) UNIQUE,
            payload TEXT NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMPTZ
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS offline_payments_staging (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key VARCHAR(255) UNIQUE,
            payload TEXT NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMPTZ
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS catalog_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_kind VARCHAR(50) NOT NULL,
            item_id BIGINT NOT NULL,
            text_content TEXT NOT NULL,
            embedding TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """))

    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_embeddings_item "
        "ON catalog_embeddings(item_kind, item_id)"
    ))


def downgrade() -> None:
    # SQLite < 3.35 does not support DROP COLUMN.
    # Columns added via ALTER TABLE are intentionally left in place to prevent data loss.
    # Tables that were created from scratch in upgrade() can be dropped safely.
    op.execute(sa.text("DROP TABLE IF EXISTS catalog_embeddings"))
    op.execute(sa.text("DROP TABLE IF EXISTS offline_payments_staging"))
    op.execute(sa.text("DROP TABLE IF EXISTS offline_sales_staging"))
    op.execute(sa.text("DROP TABLE IF EXISTS dead_letter_events"))
    op.execute(sa.text("DROP TABLE IF EXISTS client_keys"))
