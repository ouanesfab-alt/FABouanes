from __future__ import annotations

from app.core.db_access import query_db
from app.utils.pagination import paginated_rows, pagination_context, parse_pagination
from app.services.recipe_service import load_saved_recipes


def list_production_page_context(args=None):
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    q = str(args.get("q", "") or "").strip()
    production_date = str(args.get("date", "") or "").strip()
    where: list[str] = []
    params: list[object] = []
    if q:
        where.append("LOWER(fp.name || ' ' || COALESCE(pb.notes, '')) LIKE LOWER(%s)")
        params.append(f"%{q}%")
    if production_date:
        where.append("pb.production_date = %s")
        params.append(production_date)
    query = '''
        SELECT pb.*, fp.name AS finished_name
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
    '''
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY pb.id DESC"
    batches, total = paginated_rows(query_db, query, tuple(params), page=page, page_size=page_size, offset=offset)
    batch_ids = [int(batch["id"]) for batch in batches]
    recipe_by_batch: dict[int, list[str]] = {batch_id: [] for batch_id in batch_ids}
    if batch_ids:
        placeholders = ",".join(["%s"] * len(batch_ids))
        items = query_db(
            f"""
            SELECT pbi.batch_id, pbi.quantity, r.name, r.unit
            FROM production_batch_items pbi
            JOIN raw_materials r ON r.id = pbi.raw_material_id
            WHERE pbi.batch_id IN ({placeholders})
            ORDER BY pbi.batch_id, pbi.id
            """,
            tuple(batch_ids),
        )
        for item in items:
            recipe_by_batch.setdefault(int(item["batch_id"]), []).append(
                f"{item['name']} {item['quantity']} {item['unit']}"
            )
    production_rows = []
    for batch in batches:
        row = dict(batch)
        row["recipe_text"] = " + ".join(recipe_by_batch.get(int(batch["id"]), []))
        production_rows.append(row)
    return {
        'productions': production_rows,
        'filters': {'q': q, 'date': production_date},
        'pagination': pagination_context('production', args, total=total, page=page, page_size=page_size),
    }


from app.repositories.client_repository import async_compat

@async_compat
async def production_form_context():
    raw_materials = query_db('SELECT * FROM raw_materials ORDER BY name')
    return {
        'raw_materials': raw_materials,
        'raw_materials_json': [dict(r) for r in raw_materials],
        'products': query_db('SELECT * FROM finished_products ORDER BY name'),
        'recipes': await load_saved_recipes(),
    }
async def list_production_batches(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    where: list[str] = []
    params: list[object] = []
    
    if search:
        where.append("(LOWER(fp.name) LIKE LOWER(%s) OR LOWER(COALESCE(pb.notes, '')) LIKE LOWER(%s))")
        like = f"%{search}%"
        params.extend([like, like])
        
    if date_from:
        where.append("pb.production_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("pb.production_date <= %s")
        params.append(date_to)
        
    base_query = """
        SELECT pb.*, fp.name AS product_name, fp.default_unit AS product_unit
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
    """
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY production_date DESC, id DESC LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, tuple(params) + (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total


async def list_recipes(
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    from app.core.db_access import query_db_async
    
    base_query = """
        SELECT sr.*, fp.name AS finished_product_name
        FROM saved_recipes sr
        JOIN finished_products fp ON fp.id = sr.finished_product_id
    """
    
    offset = (page - 1) * page_size
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY id DESC LIMIT %s OFFSET %s"
    rows = await query_db_async(wrapped, (page_size, offset))
    total = int(rows[0]["_total_count"]) if rows else 0
    return [dict(r) for r in rows], total

