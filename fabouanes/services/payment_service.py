from __future__ import annotations

from datetime import date

from fabouanes.core.activity import log_activity
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import db_transaction, execute_db, query_db
from fabouanes.core.helpers import create_payment_record, get_open_credit_entries, reverse_payment_allocations, to_float
from fabouanes.core.perf_cache import cached_result
from fabouanes.core.storage import backup_database
from fabouanes.repositories.payment_repository import get_payment, list_payment_page_context, payment_form_context


def payments_context():
    return cached_result(("payments_context",), list_payment_page_context, ttl_seconds=6.0)


def new_payment_context():
    return payment_form_context()


def create_payment_from_form(form):
    client_raw = (form.get("client_id") or "").strip()
    if not client_raw:
        raise ValueError("Choisis un client.")
    client_id = int(client_raw)
    sale_link = form.get("sale_link") or ""
    amount = to_float(form.get("amount"))
    payment_date = form.get("payment_date") or date.today().isoformat()
    payment_type = (form.get("payment_type") or "versement").strip() or "versement"
    notes = form.get("notes", "").strip()
    payment_id = create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type)
    created = get_payment(payment_id)
    log_activity("create_payment", "payment", payment_id, f"client #{client_id} {payment_type} montant={amount}")
    audit_event("create_payment", "payment", payment_id, after=created)
    backup_database("create_payment")
    return payment_id, payment_type


def get_edit_payment_context(payment_id: int):
    payment = get_payment(payment_id)
    if not payment:
        return None
    current_link = ""
    if payment["sale_kind"] == "finished" and payment["sale_id"]:
        current_link = f"finished:{payment['sale_id']}"
    elif payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
        current_link = f"raw:{payment['raw_sale_id']}"
    open_sales = list(get_open_credit_entries())
    existing_keys = [f"{sale['item_kind']}:{sale['id']}" for sale in open_sales]
    if current_link and current_link not in existing_keys:
        if payment["sale_kind"] == "finished" and payment["sale_id"]:
            sale = query_db(
                "SELECT s.id, s.client_id, c.name AS client_name, f.name AS item_name, s.balance_due + ? AS balance_due, s.sale_date, s.total FROM sales s JOIN clients c ON c.id=s.client_id JOIN finished_products f ON f.id=s.finished_product_id WHERE s.id=?",
                (payment["amount"], payment["sale_id"]),
                one=True,
            )
            if sale:
                open_sales.append(dict(item_kind="finished", id=sale["id"], client_id=sale["client_id"], client_name=sale["client_name"], item_name=sale["item_name"], balance_due=sale["balance_due"], sale_date=sale["sale_date"], total=sale["total"]))
        elif payment["sale_kind"] == "raw" and payment["raw_sale_id"]:
            sale = query_db(
                "SELECT rs.id, rs.client_id, c.name AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, rs.balance_due + ? AS balance_due, rs.sale_date, rs.total FROM raw_sales rs JOIN clients c ON c.id=rs.client_id JOIN raw_materials r ON r.id=rs.raw_material_id WHERE rs.id=?",
                (payment["amount"], payment["raw_sale_id"]),
                one=True,
            )
            if sale:
                open_sales.append(dict(item_kind="raw", id=sale["id"], client_id=sale["client_id"], client_name=sale["client_name"], item_name=sale["item_name"], balance_due=sale["balance_due"], sale_date=sale["sale_date"], total=sale["total"]))
    return {"payment": payment, "current_link": current_link, "clients": query_db("SELECT * FROM clients ORDER BY name"), "open_sales": open_sales}


def edit_payment_from_form(payment_id: int, form):
    payment = get_payment(payment_id)
    if not payment:
        raise ValueError("Versement introuvable.")
    client_id = int(form["client_id"])
    sale_link = form.get("sale_link") or ""
    amount = to_float(form.get("amount"))
    payment_date = form.get("payment_date") or date.today().isoformat()
    notes = form.get("notes", "").strip()
    before = dict(payment)
    with db_transaction():
        reverse_payment_allocations(payment)
        execute_db("DELETE FROM payments WHERE id = ?", (payment_id,))
        new_payment_id = create_payment_record(client_id, amount, payment_date, notes, sale_link, form.get("payment_type", "versement"))
    after = get_payment(new_payment_id)
    log_activity("update_payment", "payment", payment_id, f"client #{client_id} {form.get('payment_type', 'versement')} montant={amount}")
    audit_event("update_payment", "payment", payment_id, before=before, after=after)
    backup_database("update_payment")
    return new_payment_id


def delete_payment_by_id(payment_id: int) -> bool:
    payment = get_payment(payment_id)
    if not payment:
        return False
    before = dict(payment)
    with db_transaction():
        reverse_payment_allocations(payment)
        execute_db("DELETE FROM payments WHERE id = ?", (payment_id,))
    log_activity("delete_payment", "payment", payment_id, "Suppression transaction client")
    audit_event("delete_payment", "payment", payment_id, before=before, after=None)
    backup_database("delete_payment")
    return True
