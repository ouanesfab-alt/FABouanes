SCHEMA_OPERATIONS = """
CREATE TABLE IF NOT EXISTS purchase_documents (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT REFERENCES suppliers(id) ON DELETE SET NULL,
    total DOUBLE PRECISION NOT NULL DEFAULT 0,
    purchase_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS sale_documents (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    sale_type TEXT NOT NULL CHECK(sale_type IN ('cash','credit')),
    total DOUBLE PRECISION NOT NULL DEFAULT 0,
    amount_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance_due DOUBLE PRECISION NOT NULL DEFAULT 0,
    sale_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS purchases (
    id BIGSERIAL PRIMARY KEY,
    supplier_id BIGINT REFERENCES suppliers(id) ON DELETE SET NULL,
    document_id BIGINT,
    raw_material_id BIGINT NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
    quantity DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL DEFAULT 'kg',
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    purchase_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    document_id BIGINT,
    finished_product_id BIGINT NOT NULL REFERENCES finished_products(id) ON DELETE CASCADE,
    quantity DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    sale_type TEXT NOT NULL CHECK(sale_type IN ('cash','credit')),
    amount_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance_due DOUBLE PRECISION NOT NULL DEFAULT 0,
    cost_price_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0,
    profit_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    sale_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS raw_sales (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    document_id BIGINT,
    raw_material_id BIGINT NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
    quantity DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    sale_type TEXT NOT NULL CHECK(sale_type IN ('cash','credit')),
    amount_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance_due DOUBLE PRECISION NOT NULL DEFAULT 0,
    cost_price_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0,
    profit_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    sale_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    sale_id BIGINT REFERENCES sales(id) ON DELETE SET NULL,
    raw_sale_id BIGINT REFERENCES raw_sales(id) ON DELETE SET NULL,
    sale_kind TEXT,
    payment_type TEXT NOT NULL DEFAULT 'versement',
    allocation_meta TEXT,
    amount DOUBLE PRECISION NOT NULL,
    payment_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE INDEX IF NOT EXISTS idx_sales_client_id ON sales(client_id);
CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_client_date_id ON sales(client_id, sale_date, id);
CREATE INDEX IF NOT EXISTS idx_sales_date_id ON sales(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_sales_document_id ON sales(document_id, id);
CREATE INDEX IF NOT EXISTS idx_sales_finished_product_id ON sales(finished_product_id);
CREATE INDEX IF NOT EXISTS idx_sales_type_date ON sales(sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_client_id ON raw_sales(client_id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_sale_date ON raw_sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_client_date_id ON raw_sales(client_id, sale_date, id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_date_id ON raw_sales(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_document_id ON raw_sales(document_id, id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_material_id ON raw_sales(raw_material_id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_type_date ON raw_sales(sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_payments_client_id ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_client_date_id ON payments(client_id, payment_date, id);
CREATE INDEX IF NOT EXISTS idx_payments_date_id ON payments(payment_date, id);
CREATE INDEX IF NOT EXISTS idx_payments_type_client ON payments(payment_type, client_id);
CREATE INDEX IF NOT EXISTS idx_payments_sale_id ON payments(sale_id);
CREATE INDEX IF NOT EXISTS idx_payments_raw_sale_id ON payments(raw_sale_id);
CREATE INDEX IF NOT EXISTS idx_purchases_raw_material_id ON purchases(raw_material_id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier_id ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date_id ON purchases(purchase_date, id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date_id ON purchases(supplier_id, purchase_date, id);
CREATE INDEX IF NOT EXISTS idx_purchases_document_id ON purchases(document_id, id);
CREATE INDEX IF NOT EXISTS idx_purchase_documents_date_id ON purchase_documents(purchase_date, id);
CREATE INDEX IF NOT EXISTS idx_sale_documents_date_id ON sale_documents(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_sale_documents_client_id ON sale_documents(client_id);
CREATE INDEX IF NOT EXISTS idx_purchase_documents_supplier_id ON purchase_documents(supplier_id);
"""
