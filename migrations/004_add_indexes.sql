CREATE INDEX IF NOT EXISTS idx_operations_client_id ON sales(client_id);
CREATE INDEX IF NOT EXISTS idx_operations_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_stock_product_id ON finished_products(id);

CREATE INDEX IF NOT EXISTS idx_sales_client_id ON sales(client_id);
CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_date_id ON sales(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_sales_client_date ON sales(client_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_document_id ON sales(document_id);
CREATE INDEX IF NOT EXISTS idx_sales_type_date ON sales(sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_client_type ON sales(client_id, sale_type);
CREATE INDEX IF NOT EXISTS idx_sales_type_date_client ON sales(sale_type, sale_date, client_id);

CREATE INDEX IF NOT EXISTS idx_raw_sales_client_id ON raw_sales(client_id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_sale_date ON raw_sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_date_id ON raw_sales(sale_date, id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_client_date ON raw_sales(client_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_document_id ON raw_sales(document_id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_type_date ON raw_sales(sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_client_type ON raw_sales(client_id, sale_type);
CREATE INDEX IF NOT EXISTS idx_raw_sales_type_date_client ON raw_sales(sale_type, sale_date, client_id);
CREATE INDEX IF NOT EXISTS idx_raw_sales_material_date ON raw_sales(raw_material_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_payments_client_id ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_date_id ON payments(payment_date, id);
CREATE INDEX IF NOT EXISTS idx_payments_client_date ON payments(client_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_client_type ON payments(client_id, payment_type);
CREATE INDEX IF NOT EXISTS idx_payments_type_date ON payments(payment_type, payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_sale_id ON payments(sale_id);
CREATE INDEX IF NOT EXISTS idx_payments_raw_sale_id ON payments(raw_sale_id);

CREATE INDEX IF NOT EXISTS idx_purchases_raw_material_id ON purchases(raw_material_id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier_id ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_purchase_date ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_date_id ON purchases(purchase_date, id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier_date ON purchases(supplier_id, purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_document_id ON purchases(document_id);

CREATE INDEX IF NOT EXISTS idx_prod_batch_product_id ON production_batches(finished_product_id);
CREATE INDEX IF NOT EXISTS idx_prod_batch_date ON production_batches(production_date);
CREATE INDEX IF NOT EXISTS idx_prod_batch_date_id ON production_batches(production_date, id);
CREATE INDEX IF NOT EXISTS idx_prod_batch_product_date ON production_batches(finished_product_id, production_date);
CREATE INDEX IF NOT EXISTS idx_prod_items_batch_id ON production_batch_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_prod_items_material_id ON production_batch_items(raw_material_id);

CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_raw_materials_name ON raw_materials(name);
CREATE INDEX IF NOT EXISTS idx_finished_products_name ON finished_products(name);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_action ON activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_activity_logs_username ON activity_logs(username);
CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_perf_logs_kind_created ON performance_logs(kind, created_at);
CREATE INDEX IF NOT EXISTS idx_stock_moves_item_date ON stock_movements(item_kind, item_id, created_at);
CREATE INDEX IF NOT EXISTS idx_stock_moves_reference ON stock_movements(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_username);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_status ON backup_jobs(status);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_status_created ON backup_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_backup_runs_job ON backup_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_api_refresh_tokens_user ON api_refresh_tokens(user_id);
