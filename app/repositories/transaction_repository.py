from __future__ import annotations

from urllib.parse import urlencode

from app.core.db_access import query_db
from app.core.request_state import get_state_value
from app.utils.pagination import decode_cursor, encode_cursor, keyset_pagination_context, paginated_rows, pagination_context, parse_pagination


SORT_DEFAULT_DIRECTIONS = {
    "date": "desc",
    "quantity": "desc",
    "unit_price": "desc",
    "total": "desc",
    "paid": "desc",
    "due": "desc",
}


def _normalized_sort(args) -> tuple[str, str]:
    sort_key = str(args.get("sort", "date") or "date").strip().lower()
    direction = str(args.get("direction", SORT_DEFAULT_DIRECTIONS.get(sort_key, "asc")) or "asc").strip().lower()
    allowed = {"date", "type", "partner", "designation", "quantity", "unit_price", "total", "paid", "due"}
    if sort_key not in allowed:
        sort_key = "date"
    if direction not in {"asc", "desc"}:
        direction = SORT_DEFAULT_DIRECTIONS.get(sort_key, "asc")
    return sort_key, direction


def _order_clause(sort_key: str, direction: str) -> str:
    direction_sql = "DESC" if direction == "desc" else "ASC"
    numeric_columns = {
        "quantity": "quantity",
        "unit_price": "unit_price",
        "total": "total",
        "paid": "paid",
        "due": "due",
    }
    text_columns = {
        "type": "LOWER(COALESCE(tx_type, ''))",
        "partner": "LOWER(COALESCE(partner_name, ''))",
        "designation": "LOWER(COALESCE(designation, ''))",
    }
    if sort_key in numeric_columns:
        column = numeric_columns[sort_key]
        return f"ORDER BY CASE WHEN {column} IS NULL THEN 1 ELSE 0 END ASC, {column} {direction_sql}, tx_date DESC, sort_sequence DESC, row_sort_key DESC"
    if sort_key in text_columns:
        return f"ORDER BY {text_columns[sort_key]} {direction_sql}, tx_date DESC, sort_sequence DESC, row_sort_key DESC"
    return f"ORDER BY tx_date {direction_sql}, sort_sequence {direction_sql}, row_sort_key {direction_sql}"


def _sort_url(args, sort_key: str, current_sort: str, current_direction: str) -> str:
    params = dict(args.to_dict(flat=True) if hasattr(args, "to_dict") else dict(args or {}))
    if current_sort == sort_key:
        next_direction = "desc" if current_direction == "asc" else "asc"
    else:
        next_direction = SORT_DEFAULT_DIRECTIONS.get(sort_key, "asc")
    params["sort"] = sort_key
    params["direction"] = next_direction
    params["page"] = 1
    request = get_state_value("request")
    if request is not None:
        from app.web.deps import app_url_for

        return app_url_for(request, "operations", **params)
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"/operations?{query}" if query else "/operations"


def list_transactions_context(args=None) -> dict:
    args = args or {}
    page, page_size, offset = parse_pagination(args)
    cursor = decode_cursor(str(args.get("cursor", "") or ""), 3)
    filter_type = str(args.get("type", "all") or "all").strip().lower()
    filter_name = str(args.get("name", "") or "").strip()
    filter_date = str(args.get("date", "") or "").strip()
    filter_operation = str(args.get("operation", "") or "").strip().lower()
    sort_key, sort_direction = _normalized_sort(args)

    where: list[str] = []
    params: list[object] = []
    if filter_type == "purchase":
        where.append("tx_kind = 'purchase'")
    elif filter_type == "sale":
        where.append("tx_kind IN ('sale_finished', 'sale_raw')")
    elif filter_type == "payment":
        where.append("tx_kind = 'payment'")

    if filter_name:
        where.append("LOWER(COALESCE(partner_name, '') || ' ' || COALESCE(designation, '')) LIKE LOWER(?)")
        params.append(f"%{filter_name}%")
    if filter_date:
        where.append("tx_date = %s")
        params.append(filter_date)
    if filter_operation:
        where.append("LOWER(tx_type) = LOWER(?)")
        params.append(filter_operation)

    query = """
        SELECT * FROM (
            SELECT 'Achat' AS tx_type, 'purchase' AS tx_kind, p.id, 'purchase:' || p.id AS row_sort_key,
                   COALESCE(p.document_id, p.id) AS sort_sequence, p.purchase_date AS tx_date,
                   COALESCE(s.name, '-') AS partner_name, COALESCE(NULLIF(p.custom_item_name, ''), r.name) AS designation,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.quantity / 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.quantity / 100.0
                       ELSE p.quantity
                   END AS quantity,
                   COALESCE(p.unit, r.unit, 'kg') AS unit,
                   CASE
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) = 'sac' THEN p.unit_price * 50.0
                       WHEN lower(COALESCE(p.unit, r.unit, 'kg')) IN ('qt', 'quintal') THEN p.unit_price * 100.0
                       ELSE p.unit_price
                   END AS unit_price,
                   p.total, CAST(NULL AS numeric) AS paid, CAST(NULL AS numeric) AS due, p.document_id AS document_id
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            JOIN raw_materials r ON r.id = p.raw_material_id
            UNION ALL
            SELECT 'Vente' AS tx_type,
                   CASE WHEN x.row_kind = 'finished' THEN 'sale_finished' ELSE 'sale_raw' END AS tx_kind,
                   x.id, x.row_sort_key, COALESCE(x.document_id, x.id) AS sort_sequence, x.sale_date AS tx_date, COALESCE(x.client_name, '-') AS partner_name, x.item_name AS designation,
                   x.quantity, x.unit, x.unit_price, x.total, x.amount_paid AS paid, x.balance_due AS due, x.document_id AS document_id
            FROM (
                SELECT s.id, s.document_id, 'finished' AS row_kind, 'sale_finished:' || s.id AS row_sort_key, s.sale_date, c.name AS client_name, f.name AS item_name, s.quantity, s.unit, s.unit_price, s.total, s.amount_paid, s.balance_due
                FROM sales s
                LEFT JOIN clients c ON c.id = s.client_id
                JOIN finished_products f ON f.id = s.finished_product_id
                UNION ALL
                SELECT rs.id, rs.document_id, 'raw' AS row_kind, 'sale_raw:' || rs.id AS row_sort_key, rs.sale_date, c.name AS client_name, COALESCE(NULLIF(rs.custom_item_name, ''), r.name) AS item_name, rs.quantity, rs.unit, rs.unit_price, rs.total, rs.amount_paid, rs.balance_due
                FROM raw_sales rs
                LEFT JOIN clients c ON c.id = rs.client_id
                JOIN raw_materials r ON r.id = rs.raw_material_id
            ) x
            UNION ALL
            SELECT CASE WHEN p.payment_type = 'avance' THEN 'Avance' ELSE 'Versement' END AS tx_type, 'payment' AS tx_kind,
                   p.id, 'payment:' || p.id AS row_sort_key, p.id AS sort_sequence, p.payment_date AS tx_date, c.name AS partner_name,
                   CASE
                       WHEN p.sale_kind = 'finished' AND p.sale_id IS NOT NULL THEN 'Versement vente #' || CAST(p.sale_id AS VARCHAR)
                       WHEN p.sale_kind = 'raw' AND p.raw_sale_id IS NOT NULL THEN 'Versement vente matière #' || CAST(p.raw_sale_id AS VARCHAR)
                       ELSE CASE WHEN p.payment_type = 'avance' THEN 'Avance client' ELSE 'Versement client' END
                   END AS designation,
                   CAST(NULL AS numeric) AS quantity, CAST(NULL AS varchar) AS unit, CAST(NULL AS numeric) AS unit_price, p.amount AS total, p.amount AS paid, CAST(NULL AS numeric) AS due, CAST(NULL AS integer) AS document_id
            FROM payments p
            JOIN clients c ON c.id = p.client_id
        ) t
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    total_row = query_db(f"SELECT COUNT(*) AS c FROM ({query}) transactions_count", tuple(params), one=True)
    total = int(total_row["c"] if total_row else 0)
    next_cursor = ""
    if sort_key == "date":
        cursor_where = ""
        cursor_params: list[object] = []
        if cursor:
            comparator = ">" if sort_direction == "asc" else "<"
            cursor_where = " AND " if where else " WHERE "
            try:
                cursor_sequence = int(float(cursor[1]))
            except (TypeError, ValueError):
                cursor_sequence = 0
            cursor_where += (
                f"(tx_date {comparator} ? OR "
                f"(tx_date = %s AND (sort_sequence {comparator} ? OR "
                f"(sort_sequence = %s AND row_sort_key {comparator} ?))))"
            )
            cursor_params.extend([cursor[0], cursor[0], cursor_sequence, cursor_sequence, cursor[2]])
        direction_sql = "ASC" if sort_direction == "asc" else "DESC"
        rows_plus = query_db(
            f"{query}{cursor_where} ORDER BY tx_date {direction_sql}, sort_sequence {direction_sql}, row_sort_key {direction_sql} LIMIT %s",
            tuple(params + cursor_params + [page_size + 1]),
        )
        has_next = len(rows_plus) > page_size
        rows = rows_plus[:page_size]
        if has_next and rows:
            last = rows[-1]
            next_cursor = encode_cursor(last["tx_date"], last["sort_sequence"], last["row_sort_key"])
        pagination = keyset_pagination_context(
            "operations",
            args,
            total=total,
            page=page,
            page_size=page_size,
            returned=len(rows),
            next_cursor=next_cursor,
        )
    else:
        query += " " + _order_clause(sort_key, sort_direction)
        rows, total = paginated_rows(query_db, query, tuple(params), page=page, page_size=page_size, offset=offset)
        pagination = pagination_context("operations", args, total=total, page=page, page_size=page_size)

    return {
        "transactions": rows,
        "filter_type": filter_type if filter_type in {"all", "purchase", "sale", "payment"} else "all",
        "filter_name": filter_name,
        "filter_date": filter_date,
        "filter_operation": filter_operation,
        "sort_key": sort_key,
        "sort_direction": sort_direction,
        "sort_urls": {
            key: _sort_url(args, key, sort_key, sort_direction)
            for key in ("date", "type", "partner", "designation", "quantity", "unit_price", "total", "paid", "due")
        },
        "pagination": pagination,
    }
