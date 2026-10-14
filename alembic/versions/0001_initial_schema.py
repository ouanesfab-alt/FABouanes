"""0001_initial_schema - Consolidated initial schema generated from models_pkg and core tables.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-10-14 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel

# Ensure all models are registered in SQLModel.metadata
import app.core.models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create all domain tables & indexes declared in models_pkg
    SQLModel.metadata.create_all(bind)

    # 2. Vector extension for Postgres if available
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

    # 3. Create core system and infrastructure tables
    op.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS activity_logs (
        id BIGSERIAL PRIMARY KEY,
        user_id INTEGER,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id BIGINT,
        details TEXT,
        old_value TEXT,
        new_value TEXT,
        ip_address TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);

    CREATE TABLE IF NOT EXISTS error_logs (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        route TEXT,
        error_type TEXT,
        message TEXT,
        traceback TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS system_logs (
        id BIGSERIAL PRIMARY KEY,
        level TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS performance_logs (
        id BIGSERIAL PRIMARY KEY,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        elapsed_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
        route TEXT,
        details TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_performance_logs_created_at ON performance_logs(created_at);

    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGSERIAL PRIMARY KEY,
        actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
        actor_username TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'web',
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        status TEXT NOT NULL DEFAULT 'success',
        ip_address TEXT,
        user_agent TEXT,
        request_id TEXT,
        before_json TEXT,
        after_json TEXT,
        meta_json TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);

    CREATE TABLE IF NOT EXISTS backup_jobs (
        id BIGSERIAL PRIMARY KEY,
        reason TEXT NOT NULL,
        backup_type TEXT NOT NULL DEFAULT 'event',
        local_path TEXT NOT NULL,
        requested_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        context_json TEXT,
        cloud_file_id TEXT,
        cloud_file_name TEXT,
        error_message TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS backup_runs (
        id BIGSERIAL PRIMARY KEY,
        job_id BIGINT NOT NULL REFERENCES backup_jobs(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        cloud_file_id TEXT,
        cloud_file_name TEXT,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS rate_limit_events (
        key TEXT NOT NULL,
        hit_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_hit_at ON rate_limit_events(key, hit_at);

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
    CREATE INDEX IF NOT EXISTS idx_offline_sales_status ON offline_sales_staging(status, created_at);

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
    CREATE INDEX IF NOT EXISTS idx_offline_payments_status ON offline_payments_staging(status, created_at);
    """)

    # 4. Sabrina Memory and Embeddings
    if bind.dialect.name == "postgresql":
        op.execute("""
        CREATE TABLE IF NOT EXISTS sabrina_memory (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL DEFAULT 'general',
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user_explicit',
            relevance_score REAL NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('french', content)
            ) STORED
        );
        CREATE INDEX IF NOT EXISTS idx_sabrina_memory_category ON sabrina_memory(category);
        CREATE INDEX IF NOT EXISTS idx_sabrina_memory_search ON sabrina_memory USING GIN(search_vector);
        CREATE INDEX IF NOT EXISTS idx_sabrina_memory_relevance ON sabrina_memory(relevance_score DESC);
        """)

        embed_col = "embedding vector(1536)" if has_vector else "embedding TEXT"
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS catalog_embeddings (
            id BIGSERIAL PRIMARY KEY,
            item_kind VARCHAR(50) NOT NULL,
            item_id BIGINT NOT NULL,
            text_content TEXT NOT NULL,
            {embed_col},
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_embeddings_item ON catalog_embeddings(item_kind, item_id);
        """)
    else:
        op.execute("""
        CREATE TABLE IF NOT EXISTS sabrina_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'general',
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user_explicit',
            relevance_score REAL NOT NULL DEFAULT 1.0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS catalog_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_kind TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


def downgrade() -> None:
    pass
