from __future__ import annotations

from fabouanes.core.db_access import paged_query, query_db
from fabouanes.core.helpers import get_open_credit_entries


def list_payment_page_context(*, page: int, page_size: int):
    rows, pagination = paged_query(
        """
        SELECT p.id, p.*, c.name AS client_name,
               CASE
                   WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Produit #' || p.sale_id
                   WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Matiere #' || p.raw_sale_id
                   ELSE '-'
               END AS sale_ref, p.payment_type
        FROM payments p
        JOIN clients c ON c.id = p.client_id
        ORDER BY p.id DESC
        """,
        page=page,
        page_size=page_size,
    )
    return {
        "payments": rows,
        "payments_pagination": pagination,
        "clients": query_db("SELECT * FROM clients ORDER BY name"),
        "open_sales": get_open_credit_entries(),
    }


def payment_form_context():
    return {
        "clients": query_db("SELECT * FROM clients ORDER BY name"),
        "open_sales": get_open_credit_entries(),
    }


def get_payment(payment_id: int):
    return query_db("SELECT * FROM payments WHERE id = ?", (payment_id,), one=True)
