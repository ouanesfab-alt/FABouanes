SCHEMA_CATALOG = """
CREATE TABLE IF NOT EXISTS raw_materials (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL DEFAULT 'kg',
    stock_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    sale_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    alert_threshold DOUBLE PRECISION NOT NULL DEFAULT 0,
    threshold_qty DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS finished_products (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    default_unit TEXT NOT NULL DEFAULT 'kg',
    stock_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    sale_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id BIGSERIAL PRIMARY KEY,
    item_kind TEXT NOT NULL,
    item_id BIGINT NOT NULL,
    direction TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit TEXT,
    stock_before DOUBLE PRECISION NOT NULL DEFAULT 0,
    stock_after DOUBLE PRECISION NOT NULL DEFAULT 0,
    reason TEXT,
    reference_type TEXT,
    reference_id BIGINT,
    created_by_username TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);
CREATE INDEX IF NOT EXISTS idx_raw_materials_stock_alert ON raw_materials(stock_qty, alert_threshold);
CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
"""
