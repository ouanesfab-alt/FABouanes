from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_state import get_state_value

def async_compat(func):
    """Allows an async function to be called synchronously if no event loop is running."""
    import functools
    import asyncio
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            return func(*args, **kwargs)
        else:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(func(*args, **kwargs))
    return wrapper


def db_task_compat(func):
    """
    Decorator for our newly migrated async repositories to keep full compatibility
    with callers calling it asynchronously (via await func(...) or await func.async_(...))
    or synchronously (via func(...) in a sync context).
    """
    wrapper = async_compat(func)
    wrapper.async_ = wrapper
    wrapper.sync = wrapper
    return wrapper


def to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def wants_print_after_submit() -> bool:
    form = get_state_value("submitted_form")
    return str((form or {}).get("print_after") or "").strip().lower() in {"1", "true", "on", "yes"}


def unit_choices() -> list[str]:
    from app.services.stock_service import unit_choices as _unit_choices

    return _unit_choices()


@async_compat
async def refresh_sale_profits_for_item(item_kind: str, item_id: int, avg_cost: float, sale_price: float | None = None, db: AsyncSession | None = None) -> None:
    from app.services.stock_service import refresh_sale_profits_for_item as _refresh_sale_profits_for_item

    return await _refresh_sale_profits_for_item(item_kind, item_id, avg_cost, sale_price, db=db)


@async_compat
async def get_open_credit_entries(client_id: int | None = None, db: AsyncSession | None = None):
    from app.services.client_account_service import get_open_credit_entries as _get_open_credit_entries

    return await _get_open_credit_entries(client_id, db=db)


@async_compat
async def load_saved_recipes(db: AsyncSession | None = None):
    from app.services.recipe_service import load_saved_recipes as _load_saved_recipes

    return await _load_saved_recipes(db=db)


@async_compat
async def save_recipe_definition(finished_id: int, recipe_name: str, notes: str, recipe_lines: list, user_id: int | None = None, db: AsyncSession | None = None):
    from app.services.recipe_service import save_recipe_definition as _save_recipe_definition

    return await _save_recipe_definition(finished_id, recipe_name, notes, recipe_lines, user_id, db=db)


@async_compat
async def reverse_purchase(purchase_id: int, db: AsyncSession | None = None) -> bool:
    from app.services.stock_service import reverse_purchase as _reverse_purchase

    return await _reverse_purchase(purchase_id, db=db)


@async_compat
async def reverse_sale(kind: str, row_id: int, db: AsyncSession | None = None) -> bool:
    from app.services.stock_service import reverse_sale as _reverse_sale

    return await _reverse_sale(kind, row_id, db=db)


@async_compat
async def reverse_production(batch_id: int, db: AsyncSession | None = None) -> bool:
    from app.services.stock_service import reverse_production as _reverse_production

    return await _reverse_production(batch_id, db=db)


@async_compat
async def create_purchase_record(
    supplier_id,
    item_kind_or_raw_id,
    qty: float,
    unit_price: float,
    purchase_date: str,
    notes: str,
    unit: str = "kg",
    document_id: int | None = None,
    custom_item_name: str = "",
    item_id: int | None = None,
    db: AsyncSession | None = None,
) -> int:
    from app.services.stock_service import create_purchase_record as _create_purchase_record

    return await _create_purchase_record(
        supplier_id,
        item_kind_or_raw_id,
        qty,
        unit_price,
        purchase_date,
        notes,
        unit,
        document_id,
        custom_item_name,
        item_id=item_id,
        db=db,
    )


@async_compat
async def create_sale_record(
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
    custom_item_name: str = "",
    db: AsyncSession | None = None,
):
    from app.services.stock_service import create_sale_record as _create_sale_record

    return await _create_sale_record(
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
        db=db,
    )


@async_compat
async def create_payment_record(
    client_id: int,
    amount: float,
    payment_date: str,
    notes: str,
    sale_link: str = "",
    payment_type: str = "versement",
    db: AsyncSession | None = None,
) -> int:
    from app.services.client_account_service import create_payment_record as _create_payment_record

    return await _create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type, db=db)


@async_compat
async def reverse_payment_allocations(payment_row, db: AsyncSession | None = None) -> None:
    from app.services.client_account_service import reverse_payment_allocations as _reverse_payment_allocations

    return await _reverse_payment_allocations(payment_row, db=db)


def parse_excel_client_file(file_path) -> dict:
    from app.services.excel_import_service import parse_excel_client_file as _parse_excel_client_file

    return _parse_excel_client_file(file_path)


def parse_excel_client_history(file_path) -> dict:
    from app.services.excel_import_service import parse_excel_client_history as _parse_excel_client_history

    return _parse_excel_client_history(file_path)


def init_db() -> None:
    from app.core.schema import init_db as _init_db
    return _init_db()


def log_server_start() -> None:
    from app.services.system_service import log_server_start as _log_server_start

    return _log_server_start()
