from __future__ import annotations

from app.core.db_access import execute_db, query_db, db_task


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
@db_task
def list_clients(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
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
    rows = query_db(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total


@db_task
def list_clients_with_balance(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Liste les clients avec leur solde actuel, utilisé par l'API mobile."""
    return list_clients(search, page, page_size)


