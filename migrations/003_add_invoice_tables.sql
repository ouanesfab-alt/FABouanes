CREATE TABLE IF NOT EXISTS purchase_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    total REAL NOT NULL DEFAULT 0,
    purchase_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sale_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    sale_type TEXT NOT NULL CHECK(sale_type IN ('cash','credit')),
    total REAL NOT NULL DEFAULT 0,
    amount_paid REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    sale_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_purchase_docs_date_id ON purchase_documents(purchase_date, id);
CREATE INDEX IF NOT EXISTS idx_sale_docs_date_id ON sale_documents(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_sale_docs_client_date ON sale_documents(client_id, sale_date);
