SCHEMA_CATALOG = """
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type VARCHAR(20) NOT NULL DEFAULT 'finished',
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'kg',
    stock_qty NUMERIC(15,4) NOT NULL DEFAULT 0,
    sale_price NUMERIC(15,4) NOT NULL DEFAULT 0,
    avg_cost NUMERIC(15,4) NOT NULL DEFAULT 0,
    alert_threshold NUMERIC(15,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL DEFAULT 'kg',
    stock_qty NUMERIC(14,2) NOT NULL DEFAULT 0,
    avg_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
    sale_price NUMERIC(14,2) NOT NULL DEFAULT 0,
    alert_threshold NUMERIC(14,2) NOT NULL DEFAULT 0,
    threshold_qty NUMERIC(14,2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finished_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    default_unit TEXT NOT NULL DEFAULT 'kg',
    stock_qty NUMERIC(15,4) NOT NULL DEFAULT 0,
    sale_price NUMERIC(15,4) NOT NULL DEFAULT 0,
    avg_cost NUMERIC(15,4) NOT NULL DEFAULT 0,
    alert_threshold NUMERIC(15,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_catalog_items_name ON catalog_items(name);
CREATE INDEX IF NOT EXISTS idx_catalog_items_type ON catalog_items(item_type);
CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);
CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
"""
