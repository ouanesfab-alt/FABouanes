/**
 * FABOuanes OpenAPI Generated Type Definitions
 * Auto-generated from docs/openapi.json
 */

export interface APIResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface Body_api_upload_and_restore_backup_api_admin_backups_upload_restore_post {
  file: string;
}

export interface Body_bulk_import_client_history_api_v1_clients_import_history_bulk_post {
  file: string;
}

export interface Body_import_client_history_api_v1_clients_import_history_post {
  file: string;
  client_id?: number | null;
  force_reimport?: boolean;
}

export interface ClientCreateSchema {
  name: string;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
  opening_credit?: number;
}

export interface ClientUpdateSchema {
  name: string;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
  opening_credit?: number;
}

export interface ErrorResponseSchema {
  success?: boolean;
  error: Record<string, unknown>;
}

export interface ExpenseCreateSchema {
  date: string;
  category?: string;
  description?: string | null;
  amount: number;
  payment_method?: string;
}

export interface ExpenseDetailResponse {
  success?: boolean;
  data: unknown;
}

export interface ExpenseOutSchema {
  date: string;
  category?: string;
  description?: string | null;
  amount: number;
  payment_method?: string;
  id: number;
}

export interface ExpenseUpdateSchema {
  date: string;
  category?: string;
  description?: string | null;
  amount: number;
  payment_method?: string;
}

export interface ExpensesListResponse {
  success?: boolean;
  data: unknown[];
  meta?: Record<string, unknown> | null;
}

export interface FinishedProductCreateSchema {
  name: string;
  default_unit?: string;
  stock_qty?: number | string;
  sale_price?: number | string;
  avg_cost?: number | string;
}

export interface FinishedProductUpdateSchema {
  name: string;
  default_unit: string;
  stock_qty?: number | string;
  sale_price?: number | string;
  avg_cost?: number | string;
}

export interface HTTPValidationError {
  detail?: unknown[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface PaymentCreate {
  client_id: number;
  amount: number | string;
  payment_type?: string;
  payment_date: string;
  sale_id?: number | null;
  raw_sale_id?: number | null;
  sale_kind?: string | null;
  notes?: string | null;
}

export interface PaymentCreateSchema {
  client_id: number | string;
  amount: number | string | string;
  payment_date?: string | null;
  payment_type?: string | null;
  sale_link?: string | null;
  notes?: string | null;
}

export interface ProductionCreateSchema {
  finished_product_id: number;
  output_quantity: number | string;
  production_date?: string | null;
  notes?: string | null;
  recipe_name?: string | null;
  save_recipe?: boolean | number | string | null;
  raw_material_id[]?: number[] | null;
  quantity[]?: number | string[] | null;
}

export interface PurchaseFormSchema {
  supplier_id?: number | null;
  purchase_date?: string;
  notes?: string | null;
  lines?: unknown[];
}

export interface PurchaseLineSchema {
  raw_material_id: string;
  quantity: number | string;
  unit?: string;
  unit_price: number | string;
  custom_item_name?: string | null;
}

export interface RawMaterialCreateSchema {
  name: string;
  unit?: string;
  stock_qty?: number | string;
  avg_cost?: number | string;
  sale_price?: number | string;
  alert_threshold?: number | string;
}

export interface RawMaterialUpdateSchema {
  name: string;
  unit: string;
  stock_qty?: number | string;
  avg_cost?: number | string;
  sale_price?: number | string;
  alert_threshold?: number | string;
}

export interface SaleFormSchema {
  client_id?: number | null;
  sale_type?: string | null;
  sale_date?: string;
  notes?: string | null;
  lines?: unknown[];
}

export interface SaleLineSchema {
  item_key: string;
  quantity: number | string;
  unit?: string;
  unit_price: number | string;
  custom_item_name?: string | null;
}

export interface SupplierCreateSchema {
  name: string;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface SupplierUpdateSchema {
  name: string;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface ValidationError {
  loc: string | number[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
