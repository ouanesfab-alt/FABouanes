from __future__ import annotations

from fabouanes.core.db_access import execute_db, query_db


def list_clients_with_stats():
    return query_db(
        '''
        SELECT c.*, 
               c.opening_credit
               + COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id AND s.sale_type = 'credit'), 0)
               + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id AND rs.sale_type = 'credit'), 0)
               - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type='versement'), 0)
               + COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type='avance'), 0) AS current_debt,
               COALESCE((SELECT SUM(total) FROM sales s WHERE s.client_id = c.id), 0)
               + COALESCE((SELECT SUM(total) FROM raw_sales rs WHERE rs.client_id = c.id), 0) AS total_sales,
               COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id = c.id AND p.payment_type='versement'), 0) AS total_payments
        FROM clients c
        ORDER BY c.name
        '''
    )


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
