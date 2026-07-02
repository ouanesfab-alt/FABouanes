"""gamification and badges support

Revision ID: 0034_gamification
Revises: 0033_views_and_alerts
Create Date: 2026-06-01 11:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0034_gamification'
down_revision = '0033_views_and_alerts'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add xp and level columns to users table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('users')]
    
    if 'xp' not in columns:
        op.add_column('users', sa.Column('xp', sa.Integer(), server_default='0', nullable=False))
    if 'level' not in columns:
        op.add_column('users', sa.Column('level', sa.Integer(), server_default='1', nullable=False))

    # 2. Create user_badges table
    op.execute("""
    CREATE TABLE IF NOT EXISTS user_badges (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        badge_name VARCHAR(50) NOT NULL,
        badge_title VARCHAR(100) NOT NULL,
        badge_description TEXT NOT NULL,
        unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_user_id ON user_badges(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_badge_name ON user_badges(badge_name)")

def downgrade() -> None:
    # 1. Drop user_badges table
    op.execute("DROP INDEX IF EXISTS idx_user_badges_badge_name")
    op.execute("DROP INDEX IF EXISTS idx_user_badges_user_id")
    op.execute("DROP TABLE IF EXISTS user_badges")

    # 2. Drop columns from users table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('users')]
    
    if 'xp' in columns:
        op.drop_column('users', 'xp')
    if 'level' in columns:
        op.drop_column('users', 'level')
