"""Tables SQL du module Dépenses & Charges."""

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS expenses (
        id BIGSERIAL PRIMARY KEY,
        date DATE NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        description TEXT,
        amount DOUBLE PRECISION NOT NULL DEFAULT 0,
        payment_method TEXT DEFAULT 'cash'
            CHECK(payment_method IN ('cash', 'cheque', 'virement', 'autre')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]
