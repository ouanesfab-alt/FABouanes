"""
0035 - Correction des types de donnees financiers et dates.

- expenses.amount: float -> NUMERIC(15,4) pour la coherence financiere
- imported_client_history.entry_date: TEXT -> DATE pour le tri/filtre SQL correct
"""
from __future__ import annotations

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. expenses.amount : float -> NUMERIC(15,4)
    op.execute("UPDATE expenses SET amount = 0 WHERE amount IS NULL")
    op.execute(
        """
        ALTER TABLE expenses
        ALTER COLUMN amount TYPE NUMERIC(15,4)
        USING ROUND(amount::NUMERIC, 4)
        """
    )

    # 2. imported_client_history.entry_date : TEXT -> DATE
    op.execute(
        """
        ALTER TABLE imported_client_history
        ALTER COLUMN entry_date TYPE DATE
        USING (
            CASE
                WHEN entry_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN entry_date::DATE
                ELSE CURRENT_DATE
            END
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE imported_client_history
        ALTER COLUMN entry_date TYPE TEXT
        USING entry_date::TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE expenses
        ALTER COLUMN amount TYPE FLOAT
        USING amount::FLOAT
        """
    )
