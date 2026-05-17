SCHEMA_PRODUCTION = """
CREATE TABLE IF NOT EXISTS production_batches (
    id BIGSERIAL PRIMARY KEY,
    finished_product_id BIGINT NOT NULL REFERENCES finished_products(id) ON DELETE CASCADE,
    output_quantity DOUBLE PRECISION NOT NULL,
    production_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    production_date TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS production_batch_items (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
    raw_material_id BIGINT NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
    quantity DOUBLE PRECISION NOT NULL,
    unit_cost_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0,
    line_cost DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saved_recipes (
    id BIGSERIAL PRIMARY KEY,
    finished_product_id BIGINT NOT NULL REFERENCES finished_products(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    notes TEXT,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS saved_recipe_items (
    id BIGSERIAL PRIMARY KEY,
    recipe_id BIGINT NOT NULL REFERENCES saved_recipes(id) ON DELETE CASCADE,
    raw_material_id BIGINT NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
    quantity DOUBLE PRECISION NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prod_batch_product_id ON production_batches(finished_product_id);
CREATE INDEX IF NOT EXISTS idx_prod_batch_date_id ON production_batches(production_date, id);
CREATE INDEX IF NOT EXISTS idx_prod_items_batch_id ON production_batch_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_saved_recipes_product ON saved_recipes(finished_product_id);
CREATE INDEX IF NOT EXISTS idx_saved_recipe_items_recipe ON saved_recipe_items(recipe_id);
"""
