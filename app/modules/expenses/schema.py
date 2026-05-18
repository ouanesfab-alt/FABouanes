"""Tables SQL du module Dépenses & Charges."""

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS expenses (
        id BIGSERIAL PRIMARY KEY,
        date TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        description TEXT,
        amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        payment_method TEXT DEFAULT 'cash'
            CHECK(payment_method IN ('cash', 'cheque', 'virement', 'autre')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
]
