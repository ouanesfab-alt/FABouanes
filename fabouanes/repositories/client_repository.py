from __future__ import annotations

from fabouanes.core.db_access import execute_db, paged_query, query_db


def list_clients_with_stats(*, page: int, page_size: int, search: str = ""):
    search_text = str(search or "").strip()
    where = ""
    params: list[object] = []
    if search_text:
        where = """
        WHERE
            LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
            OR LOWER(COALESCE(c.phone, '')) LIKE LOWER(?)
            OR LOWER(COALESCE(c.address, '')) LIKE LOWER(?)
        """
        like_value = f"%{search_text}%"
        params.extend([like_value, like_value, like_value])
    query = f"""
        WITH sales_totals AS (
            SELECT
                client_id,
                COALESCE(SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END), 0) AS credit_total,
                COALESCE(SUM(total), 0) AS total_sales
            FROM sales
            GROUP BY client_id
        ),
        raw_sales_totals AS (
            SELECT
                client_id,
                COALESCE(SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END), 0) AS credit_total,
                COALESCE(SUM(total), 0) AS total_sales
            FROM raw_sales
            GROUP BY client_id
        ),
        payment_totals AS (
            SELECT
                client_id,
                COALESCE(SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END), 0) AS total_payments,
                COALESCE(SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END), 0) AS total_advance
            FROM payments
            GROUP BY client_id
        )
        SELECT
            c.*,
            c.opening_credit
                + COALESCE(st.credit_total, 0)
                + COALESCE(rst.credit_total, 0)
                - COALESCE(pt.total_payments, 0)
                + COALESCE(pt.total_advance, 0) AS current_debt,
            COALESCE(st.total_sales, 0) + COALESCE(rst.total_sales, 0) AS total_sales,
            COALESCE(pt.total_payments, 0) AS total_payments
        FROM clients c
        LEFT JOIN sales_totals st ON st.client_id = c.id
        LEFT JOIN raw_sales_totals rst ON rst.client_id = c.id
        LEFT JOIN payment_totals pt ON pt.client_id = c.id
        {where}
        ORDER BY c.name
    """
    rows, pagination = paged_query(query, tuple(params), page=page, page_size=page_size)
    return rows, pagination


def insert_client(name: str, phone: str, address: str, notes: str, opening_credit: float):
    return execute_db(
        'INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (?, ?, ?, ?, ?)',
        (name, phone, address, notes, opening_credit),
    )


def get_client(client_id: int):
    return query_db('SELECT * FROM clients WHERE id = ?', (client_id,), one=True)


def update_client(client_id: int, name: str, phone: str, address: str, notes: str, opening_credit: float):
    execute_db(
        'UPDATE clients SET name=?, phone=?, address=?, notes=?, opening_credit=? WHERE id=?',
        (name, phone, address, notes, opening_credit, client_id),
    )


def find_client_by_name(name: str):
    return query_db('SELECT id FROM clients WHERE lower(trim(name)) = lower(trim(?))', (name,), one=True)
