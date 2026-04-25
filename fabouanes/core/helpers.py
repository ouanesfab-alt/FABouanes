from __future__ import annotations

from flask import request

# Thin wrappers to isolate the historical runtime core from routes/services/repositories.
# Business logic remains centralized for now to preserve stability.

def _rt():
    from fabouanes import runtime_app
    return runtime_app

def to_float(value: str | None, default: float = 0.0) -> float:
    return _rt().to_float(value, default)

def wants_print_after_submit() -> bool:
    return _rt().wants_print_after_submit()

def unit_choices() -> list[str]:
    return _rt().unit_choices()

def get_open_credit_entries(client_id: int | None = None):
    return _rt().get_open_credit_entries(client_id)

def load_saved_recipes():
    return _rt().load_saved_recipes()

def save_recipe_definition(finished_id: int, recipe_name: str, notes: str, recipe_lines: list, user_id: int | None = None):
    return _rt().save_recipe_definition(finished_id, recipe_name, notes, recipe_lines, user_id)

def reverse_purchase(purchase_id: int) -> bool:
    return _rt().reverse_purchase(purchase_id)

def reverse_sale(kind: str, row_id: int) -> bool:
    return _rt().reverse_sale(kind, row_id)

def reverse_production(batch_id: int) -> bool:
    return _rt().reverse_production(batch_id)

def create_purchase_record(
    supplier_id,
    raw_id: int,
    qty: float,
    unit_price: float,
    purchase_date: str,
    notes: str,
    unit: str = 'kg',
    document_id: int | None = None,
    custom_item_name: str = '',
) -> int:
    return _rt().create_purchase_record(
        supplier_id,
        raw_id,
        qty,
        unit_price,
        purchase_date,
        notes,
        unit,
        document_id,
        custom_item_name,
    )

def create_sale_record(
    client_id,
    item_kind: str,
    item_id: int,
    qty: float,
    unit: str,
    unit_price: float,
    sale_type: str,
    sale_date: str,
    notes: str,
    amount_paid_input: float = 0,
    document_id: int | None = None,
    custom_item_name: str = '',
):
    return _rt().create_sale_record(
        client_id,
        item_kind,
        item_id,
        qty,
        unit,
        unit_price,
        sale_type,
        sale_date,
        notes,
        amount_paid_input,
        document_id,
        custom_item_name,
    )

def create_payment_record(client_id: int, amount: float, payment_date: str, notes: str, sale_link: str = '', payment_type: str = 'versement') -> int:
    return _rt().create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type)

def reverse_payment_allocations(payment_row) -> None:
    return _rt().reverse_payment_allocations(payment_row)

def parse_excel_client_file(file_path) -> dict:
    return _rt().parse_excel_client_file(file_path)

def parse_excel_client_history(file_path) -> dict:
    return _rt().parse_excel_client_history(file_path)

def init_db() -> None:
    return _rt().init_db()

def log_server_start() -> None:
    return _rt().log_server_start()
