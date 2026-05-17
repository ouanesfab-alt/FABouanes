SCHEMA_CONTACTS = """
CREATE TABLE IF NOT EXISTS clients (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    opening_credit NUMERIC(14,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector tsvector
);

CREATE TABLE IF NOT EXISTS suppliers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS imported_client_history (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_file TEXT,
    entry_date TEXT NOT NULL,
    designation TEXT,
    debit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    running_balance NUMERIC(14,2) NOT NULL DEFAULT 0,
    imported_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);
CREATE INDEX IF NOT EXISTS idx_suppliers_phone ON suppliers(phone);
CREATE INDEX IF NOT EXISTS idx_clients_fts ON clients USING GIN(search_vector);

DROP TRIGGER IF EXISTS trg_clients_fts ON clients;
CREATE OR REPLACE FUNCTION update_clients_search_vector() RETURNS TRIGGER AS $$
BEGIN
  NEW.search_vector := to_tsvector('french',
    COALESCE(NEW.name,'') || ' ' || COALESCE(NEW.phone,'') || ' ' || COALESCE(NEW.address,''));
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_clients_fts BEFORE INSERT OR UPDATE ON clients
  FOR EACH ROW EXECUTE FUNCTION update_clients_search_vector();
"""
