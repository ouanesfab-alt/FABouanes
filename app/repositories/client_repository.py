from __future__ import annotations

from app.core.db_access import execute_db, query_db, db_task
from app.utils.pagination import pagination_context, parse_pagination
def client_stats_query(where_sql: str = "") -> str:
    where_clause = f"WHERE {where_sql}" if where_sql else ""
    return f"SELECT * FROM clients_with_stats {where_clause}"


@db_task
def list_clients_with_stats():
    return query_db(f"{client_stats_query()} ORDER BY name")


@db_task
def list_clients_page_context(args=None):
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    search = str(args.get("q", "") or "").strip()
    where_sql = ""
    params: list[object] = []
    if search:
        where_sql = "search_vector @@ plainto_tsquery('french', %s)"
        params.append(search)

    where_clause = f"WHERE {where_sql}" if where_sql else ""
    total_row = query_db(f"SELECT COUNT(*) AS c FROM clients_with_stats {where_clause}", tuple(params), one=True)
    total = int(total_row["c"] if total_row else 0)
    rows = query_db(
        f"SELECT * FROM clients_with_stats {where_clause} ORDER BY name LIMIT %s OFFSET %s",
        tuple(params) + (page_size, offset),
    )
    return {
        "clients": rows,
        "client_filters": {"q": search},
        "pagination": pagination_context("clients", args, total=total, page=page, page_size=page_size),
    }


@db_task
def get_client_with_stats(client_id: int):
    return query_db(client_stats_query("c.id = %s"), (client_id,), one=True)


@db_task
def insert_client(name: str, phone: str, address: str, notes: str, opening_credit: float):
    return execute_db(
        'INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)',
        (name, phone, address, notes, opening_credit),
    )


@db_task
def get_client(client_id: int):
    return query_db('SELECT * FROM clients WHERE id = %s', (client_id,), one=True)


@db_task
def update_client(client_id: int, name: str, phone: str, address: str, notes: str, opening_credit: float):
    execute_db(
        'UPDATE clients SET name=%s, phone=%s, address=%s, notes=%s, opening_credit=%s WHERE id=%s',
        (name, phone, address, notes, opening_credit, client_id),
    )


@db_task
def find_client_by_name(name: str):
    return query_db('SELECT id FROM clients WHERE lower(trim(name)) = lower(trim(%s))', (name,), one=True)
async def list_clients(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("search_vector @@ plainto_tsquery('french', %s)")
        params.append(search)
        
    base_query = "SELECT * FROM clients_with_stats"
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total

