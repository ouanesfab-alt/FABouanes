from __future__ import annotations

from app.core.db_access import execute_db, query_db
from app.utils.pagination import pagination_context, parse_pagination
from app.core.search import fts_query, sqlite_fts_enabled


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
        SELECT c.id, c.name, c.phone, c.address, c.notes, c.opening_credit, c.created_at,
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


def list_clients_page_context(args=None):
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    search = str(args.get("q", "") or "").strip()
    where_sql = ""
    params: list[object] = []
    if search:
        fts = fts_query(search)
        if fts and sqlite_fts_enabled("clients_fts"):
            where_sql = "c.id IN (SELECT rowid FROM clients_fts WHERE clients_fts MATCH ?)"
            params.append(fts)
        else:
            where_sql = "(LOWER(c.name) LIKE LOWER(?) OR LOWER(COALESCE(c.phone, '')) LIKE LOWER(?) OR LOWER(COALESCE(c.address, '')) LIKE LOWER(?))"
            params.extend([f"%{search}%"] * 3)

    where_clause = f"WHERE {where_sql}" if where_sql else ""
    total_row = query_db(f"SELECT COUNT(*) AS c FROM clients c {where_clause}", tuple(params), one=True)
    total = int(total_row["c"] if total_row else 0)
    rows = query_db(
        f"""
        WITH page_clients AS (
            SELECT c.id, c.name, c.phone, c.address, c.notes, c.opening_credit, c.created_at
            FROM clients c
            {where_clause}
            ORDER BY c.name
            LIMIT ? OFFSET ?
        ),
        finished_totals AS (
            SELECT client_id,
                   SUM(total) AS total_sales,
                   SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
            FROM sales
            WHERE client_id IN (SELECT id FROM page_clients)
            GROUP BY client_id
        ),
        raw_totals AS (
            SELECT client_id,
                   SUM(total) AS total_sales,
                   SUM(CASE WHEN sale_type = 'credit' THEN total ELSE 0 END) AS credit_total
            FROM raw_sales
            WHERE client_id IN (SELECT id FROM page_clients)
            GROUP BY client_id
        ),
        payment_totals AS (
            SELECT client_id,
                   SUM(CASE WHEN payment_type = 'versement' THEN amount ELSE 0 END) AS versements,
                   SUM(CASE WHEN payment_type = 'avance' THEN amount ELSE 0 END) AS avances
            FROM payments
            WHERE client_id IN (SELECT id FROM page_clients)
            GROUP BY client_id
        )
        SELECT pc.*,
               pc.opening_credit
               + COALESCE(ft.credit_total, 0)
               + COALESCE(rt.credit_total, 0)
               - COALESCE(pt.versements, 0)
               + COALESCE(pt.avances, 0) AS current_debt,
               pc.opening_credit
               + COALESCE(ft.credit_total, 0)
               + COALESCE(rt.credit_total, 0)
               - COALESCE(pt.versements, 0)
               + COALESCE(pt.avances, 0) AS current_balance,
               COALESCE(ft.total_sales, 0) + COALESCE(rt.total_sales, 0) AS total_sales,
               COALESCE(pt.versements, 0) AS total_payments
        FROM page_clients pc
        LEFT JOIN finished_totals ft ON ft.client_id = pc.id
        LEFT JOIN raw_totals rt ON rt.client_id = pc.id
        LEFT JOIN payment_totals pt ON pt.client_id = pc.id
        ORDER BY pc.name
        """,
        tuple(params) + (page_size, offset),
    )
    return {
        "clients": rows,
        "client_filters": {"q": search},
        "pagination": pagination_context("clients", args, total=total, page=page, page_size=page_size),
    }


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
async def list_clients(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    from app.api.v1._common import client_balance_sql, client_total_sales_sql, client_total_payments_sql
    
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(c.name) LIKE LOWER(?) OR LOWER(COALESCE(c.phone, '')) LIKE LOWER(?) OR LOWER(COALESCE(c.address, '')) LIKE LOWER(?))")
        like = f"%{search}%"
        params.extend([like, like, like])
        
    base_query = f"""
        SELECT c.*,
               {client_balance_sql("c")} AS current_balance,
               {client_balance_sql("c")} AS current_debt,
               {client_total_sales_sql("c")} AS total_sales,
               {client_total_payments_sql("c")} AS total_payments
        FROM clients c
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    from app.core.config import settings
    offset = (page - 1) * page_size
    
    if settings.uses_postgres:
        wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT ? OFFSET ?"
        rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
        total = int(rows[0]["_total_count"]) if rows else 0
        return [dict(r) for r in rows], total
        
    count_row = await query_db_async(f"SELECT COUNT(*) AS c FROM ({base_query}) _q", tuple(params), one=True)
    total = int(count_row["c"] if count_row else 0)
    
    rows = await query_db_async(f"{base_query} ORDER BY c.name LIMIT ? OFFSET ?", tuple(params) + (page_size, offset))
    return [dict(r) for r in rows], total

