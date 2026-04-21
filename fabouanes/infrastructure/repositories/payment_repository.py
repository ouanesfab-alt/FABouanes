from __future__ import annotations

from typing import Any

from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.helpers import create_payment_record, get_open_credit_entries, reverse_payment_allocations
from fabouanes.repositories.payment_repository import (
    get_payment as get_legacy_payment,
    list_payment_page_context,
    payment_form_context,
)


class SQLitePaymentRepository:
    def list_payment_page_context(self) -> dict[str, Any]:
        return list_payment_page_context()

    def payment_form_context(self) -> dict[str, Any]:
        return payment_form_context()

    def get_payment(self, payment_id: int):
        return get_legacy_payment(payment_id)

    def list_clients(self):
        return query_db("SELECT * FROM clients ORDER BY name")

    def list_open_credit_entries(self):
        return get_open_credit_entries()

    def client_exists(self, client_id: int) -> bool:
        return bool(query_db("SELECT 1 FROM clients WHERE id = ?", (client_id,), one=True))

    def create_payment(
        self,
        *,
        client_id: int,
        amount: float,
        payment_date: str,
        notes: str,
        sale_link: str,
        payment_type: str,
    ) -> int:
        return create_payment_record(client_id, amount, payment_date, notes, sale_link, payment_type)

    def reverse_payment_allocations(self, payment_row) -> None:
        reverse_payment_allocations(payment_row)

    def delete_payment(self, payment_id: int) -> None:
        execute_db("DELETE FROM payments WHERE id = ?", (payment_id,))

    def get_finished_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float) -> dict[str, Any] | None:
        sale = query_db(
            """
            SELECT s.id, s.client_id, c.name AS client_name, f.name AS item_name,
                   s.balance_due + ? AS balance_due, s.sale_date, s.total
            FROM sales s
            JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            WHERE s.id = ?
            """,
            (restored_amount, sale_id),
            one=True,
        )
        if not sale:
            return None
        return dict(
            item_kind="finished",
            id=sale["id"],
            client_id=sale["client_id"],
            client_name=sale["client_name"],
            item_name=sale["item_name"],
            balance_due=sale["balance_due"],
            sale_date=sale["sale_date"],
            total=sale["total"],
        )

    def get_raw_sale_credit_entry_for_payment(self, sale_id: int, restored_amount: float) -> dict[str, Any] | None:
        sale = query_db(
            """
            SELECT rs.id, rs.client_id, c.name AS client_name,
                   COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name,
                   rs.balance_due + ? AS balance_due, rs.sale_date, rs.total
            FROM raw_sales rs
            JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            WHERE rs.id = ?
            """,
            (restored_amount, sale_id),
            one=True,
        )
        if not sale:
            return None
        return dict(
            item_kind="raw",
            id=sale["id"],
            client_id=sale["client_id"],
            client_name=sale["client_name"],
            item_name=sale["item_name"],
            balance_due=sale["balance_due"],
            sale_date=sale["sale_date"],
            total=sale["total"],
        )

