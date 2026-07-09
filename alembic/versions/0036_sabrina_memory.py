"""
0036 - Sabrina Memory: mémoire persistante pour l'assistante IA.

Permet à Sabrina de mémoriser des préférences, contextes et corrections
entre les sessions de conversation.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0036_sabrina_memory"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sabrina_memory CASCADE;")
