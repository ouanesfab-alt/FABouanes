"""consolidate schema_bootstrap DDL into canonical alembic migration

Revision ID: 0041_consolidate_bootstrap
Revises: 0040_fix_stats_advances
Create Date: 2026-10-03 13:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0041_consolidate_bootstrap"
down_revision = "0040_fix_stats_advances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # 1. Rate limiting & event tracking tables
    op.execute("""
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

    CREATE TABLE IF NOT EXISTS offline_sales_staging (
        id BIGSERIAL PRIMARY KEY,
        idempotency_key VARCHAR(255) UNIQUE,
        payload TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'pending',
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        locked_at TIMESTAMPTZ,
        processed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS offline_payments_staging (
        id BIGSERIAL PRIMARY KEY,
        idempotency_key VARCHAR(255) UNIQUE,
        payload TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'pending',
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        locked_at TIMESTAMPTZ,
        processed_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_offline_sales_status ON offline_sales_staging(status, created_at);
    CREATE INDEX IF NOT EXISTS idx_offline_payments_status ON offline_payments_staging(status, created_at);

    CREATE TABLE IF NOT EXISTS production_batches (
        id SERIAL PRIMARY KEY,
        batch_code TEXT UNIQUE,
        finished_product_id INTEGER NOT NULL REFERENCES finished_products(id) ON DELETE CASCADE,
        production_date DATE NOT NULL,
        output_quantity NUMERIC(14, 3) NOT NULL,
        production_cost NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        unit_cost NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        notes TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS production_batch_items (
        id SERIAL PRIMARY KEY,
        batch_id INTEGER NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
        raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
        quantity_used NUMERIC(14, 3) NOT NULL,
        unit_cost NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        total_cost NUMERIC(14, 2) NOT NULL DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS saved_recipes (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        finished_product_id INTEGER REFERENCES finished_products(id) ON DELETE SET NULL,
        target_quantity NUMERIC(14, 3) NOT NULL DEFAULT 1.0,
        target_unit TEXT NOT NULL DEFAULT 'kg',
        description TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS saved_recipe_items (
        id SERIAL PRIMARY KEY,
        recipe_id INTEGER NOT NULL REFERENCES saved_recipes(id) ON DELETE CASCADE,
        raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
        quantity NUMERIC(14, 3) NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg'
    );
    """)

    # 2. Add columns if missing in core tables
    if "users" in tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "custom_permissions_json" not in user_cols:
            op.add_column("users", sa.Column("custom_permissions_json", sa.Text(), server_default="[]"))
        if "failed_login_count" not in user_cols:
            op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
        if "locked_until" not in user_cols:
            op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    for tbl in ("purchases", "sales", "raw_sales", "payments"):
        if tbl in tables:
            tbl_cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "created_at" not in tbl_cols:
                op.add_column(tbl, sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))

    if "purchases" in tables:
        purch_cols = {c["name"] for c in inspector.get_columns("purchases")}
        if "finished_product_id" not in purch_cols:
            op.add_column("purchases", sa.Column("finished_product_id", sa.BigInteger(), sa.ForeignKey("finished_products.id", ondelete="CASCADE"), nullable=True))
        try:
            op.alter_column("purchases", "raw_material_id", nullable=True)
        except Exception:
            pass

    if "outbox_events" in tables:
        outbox_cols = {c["name"] for c in inspector.get_columns("outbox_events")}
        if "retry_count" not in outbox_cols:
            op.add_column("outbox_events", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        if "last_error" not in outbox_cols:
            op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))

    # 3. Vector embeddings table if vector extension is available, else fallback text
    has_vector = False
    try:
        res = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector' AND installed_version IS NOT NULL;")).fetchone()
        if res:
            has_vector = True
        else:
            avail = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';")).fetchone()
            if avail:
                bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
                has_vector = True
    except Exception:
        has_vector = False

    if has_vector:
        op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_embeddings (
            id BIGSERIAL PRIMARY KEY,
            item_kind VARCHAR(50) NOT NULL,
            item_id BIGINT NOT NULL,
            text_content TEXT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_embeddings_item ON catalog_embeddings(item_kind, item_id);
        """)
    else:
        op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_embeddings (
            id BIGSERIAL PRIMARY KEY,
            item_kind VARCHAR(50) NOT NULL,
            item_id BIGINT NOT NULL,
            text_content TEXT NOT NULL,
            embedding TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_embeddings_item ON catalog_embeddings(item_kind, item_id);
        """)

    # 4. Composite & Search Indexes
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_sales_credit_client ON sales(client_id, total) WHERE sale_type = 'credit';
    CREATE INDEX IF NOT EXISTS idx_raw_sales_credit_client ON raw_sales(client_id, total) WHERE sale_type = 'credit';
    CREATE INDEX IF NOT EXISTS idx_sales_client_date_type ON sales(client_id, sale_date, sale_type);
    CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date ON purchases(supplier_id, purchase_date);
    CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
    CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);
    CREATE INDEX IF NOT EXISTS idx_purchases_finished_product_id ON purchases(finished_product_id);
    CREATE INDEX IF NOT EXISTS idx_prod_items_material_id ON production_batch_items(raw_material_id);
    CREATE INDEX IF NOT EXISTS idx_saved_recipe_items_material_id ON saved_recipe_items(raw_material_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);
    CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_performance_logs_created_at ON performance_logs(created_at);
    CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
    CREATE INDEX IF NOT EXISTS idx_purchases_purchase_date ON purchases(purchase_date);
    CREATE INDEX IF NOT EXISTS idx_payments_client_date ON payments(client_id, payment_date);
    CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
    """)

    if "expenses" in tables:
        op.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);")
    if "stock_movements" in tables:
        op.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_kind, item_id);")


def downgrade() -> None:
    pass
