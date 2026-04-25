from __future__ import annotations

from fabouanes.core.db_access import execute_db, query_db


def client_stats_query(where_sql: str = "") -> str:
    where_clause = f"WHERE {where_sql}" if where_sql else ""
    return f"""
        WITH finished_totals AS (
            SELECT client_id,
                   SUM(total) AS total_sales,
                   SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
            FROM sales
            WHERE client_id IS NOT NULL
            GROUP BY client_id
        ),
        raw_totals AS (
            SELECT client_id,
                   SUM(total) AS total_sales,
                   SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
            FROM raw_sales
            WHERE client_id IS NOT NULL
            GROUP BY client_id
        ),
        payment_totals AS (
            SELECT client_id,
                   SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END) AS versements,
                   SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END) AS avances
            FROM payments
            GROUP BY client_id
        )
        SELECT c.*,
               c.opening_credit
               + COALESCE(ft.credit_total, 0)
               + COALESCE(rt.credit_total, 0)
               - COALESCE(pt.versements, 0)
               + COALESCE(pt.avances, 0) AS current_debt,
               c.opening_credit
               + COALESCE(ft.credit_total, 0)
               + COALESCE(rt.credit_total, 0)
               - COALESCE(pt.versements, 0)
               + COALESCE(pt.avances, 0) AS current_balance,
               COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
               COALESCE(pt.versements, 0) AS total_payments
        FROM clients c
        LEFT JOIN finished_totals ft ON ft.client_id = c.id
        LEFT JOIN raw_totals rt ON rt.client_id = c.id
        LEFT JOIN payment_totals pt ON pt.client_id = c.id
        {where_clause}
    """


def list_clients_with_stats():
    return query_db(f"{client_stats_query()} ORDER BY c.name")


def get_client_with_stats(client_id: int):
    return query_db(client_stats_query("c.id = ?"), (client_id,), one=True)


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
