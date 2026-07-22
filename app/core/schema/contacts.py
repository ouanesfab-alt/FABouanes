SCHEMA_CONTACTS = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_type VARCHAR(20) NOT NULL DEFAULT 'client',
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    opening_credit NUMERIC(14,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    search_vector TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    opening_credit NUMERIC(14,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    search_vector TEXT
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS imported_client_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_file TEXT,
    entry_date TEXT NOT NULL,
    designation TEXT,
    debit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    running_balance NUMERIC(14,2) NOT NULL DEFAULT 0,
    imported_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);
CREATE INDEX IF NOT EXISTS idx_suppliers_phone ON suppliers(phone);

CREATE VIEW IF NOT EXISTS clients_with_stats AS
WITH finished_totals AS (
    SELECT client_id,
           SUM(total) AS total_sales,
           SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
    FROM sales
    WHERE client_id IS NOT NULL
    GROUP BY client_id
),
raw_totals AS (
    SELECT client_id,
           SUM(total) AS total_sales,
           SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
    FROM raw_sales
    WHERE client_id IS NOT NULL
    GROUP BY client_id
),
payment_totals AS (
    SELECT client_id,
           SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END) AS versements,
           SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END) AS avances
    FROM payments
    GROUP BY client_id
)
SELECT c.id, c.name, c.phone, c.address, c.notes, c.opening_credit, c.created_at, c.search_vector,
       c.opening_credit
       + COALESCE(ft.credit_total, 0)
       + COALESCE(rt.credit_total, 0)
       - COALESCE(pt.versements, 0)
       + COALESCE(pt.avances, 0) AS current_debt,
       c.opening_credit
       + COALESCE(ft.credit_total, 0)
       + COALESCE(rt.credit_total, 0)
       - COALESCE(pt.versements, 0)
       + COALESCE(pt.avances, 0) AS current_balance,
       COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
       COALESCE(pt.versements, 0) AS total_payments
FROM clients c
LEFT JOIN finished_totals ft ON ft.client_id = c.id
LEFT JOIN raw_totals rt ON rt.client_id = c.id
LEFT JOIN payment_totals pt ON pt.client_id = c.id;

CREATE VIEW IF NOT EXISTS mv_client_balances AS
SELECT 
    id AS client_id,
    name,
    current_balance AS balance
FROM clients_with_stats;
"""
