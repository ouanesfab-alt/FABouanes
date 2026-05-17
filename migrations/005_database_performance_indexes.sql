CREATE INDEX IF NOT EXISTS idx_sale_documents_date_client ON sale_documents(sale_date, client_id);
CREATE INDEX IF NOT EXISTS idx_purchase_documents_date_supplier ON purchase_documents(purchase_date, supplier_id);

CREATE INDEX IF NOT EXISTS idx_sales_dashboard_day ON sales(sale_date, total, profit_amount);
CREATE INDEX IF NOT EXISTS idx_raw_sales_dashboard_day ON raw_sales(sale_date, total, profit_amount);
CREATE INDEX IF NOT EXISTS idx_payments_dashboard_day ON payments(payment_date, amount);

CREATE INDEX IF NOT EXISTS idx_sales_credit_client_day ON sales(client_id, sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_credit_client_day ON raw_sales(client_id, sale_type, sale_date);
CREATE INDEX IF NOT EXISTS idx_payments_client_type_day_amount ON payments(client_id, payment_type, payment_date, amount);

CREATE INDEX IF NOT EXISTS idx_sales_product_day ON sales(finished_product_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_raw_sales_material_day ON raw_sales(raw_material_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_production_items_material_batch ON production_batch_items(raw_material_id, batch_id);
CREATE INDEX IF NOT EXISTS idx_imported_client_history_client_date ON imported_client_history(client_id, entry_date);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_created ON audit_logs(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_entity_created ON activity_logs(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_performance_logs_created ON performance_logs(created_at);
