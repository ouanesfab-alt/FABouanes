from __future__ import annotations

from app.api.v1.form_parsers import (
    payload_to_form_data,
)
from app.api.v1.query_builders import (
    append_date_range,
    append_text_search,
    like_value,
    pagination_meta,
    query_list_async,
)
from app.api.v1.response_helpers import (
    client_history_payload,
    client_payload,
    filtered_sellable_items,
    finished_product_payload,
    json_response,
    payment_payload,
    production_payload,
    purchase_document_payload,
    purchase_payload,
    raw_material_payload,
    sale_document_payload,
    sale_payload,
    supplier_payload,
)

# Also export core database functions as some files import them from here
from app.core.db_helpers import (
    query_db,
    query_db_async,
)

__all__ = [
    "query_db",
    "query_db_async",
    "payload_to_form_data",
    "pagination_meta",
    "query_list_async",
    "like_value",
    "append_text_search",
    "append_date_range",
    "json_response",
    "client_payload",
    "supplier_payload",
    "raw_material_payload",
    "finished_product_payload",
    "production_payload",
    "purchase_payload",
    "sale_payload",
    "purchase_document_payload",
    "sale_document_payload",
    "payment_payload",
    "client_history_payload",
    "filtered_sellable_items",
    "add_cache_headers",
]


def add_cache_headers(request, response, response_data, max_age: int = 30) -> None:
    import hashlib
    import json

    from fastapi import HTTPException

    # Generate ETag
    serialized = json.dumps(response_data, sort_keys=True, default=str)
    etag = f'"{hashlib.md5(serialized.encode("utf-8"), usedforsecurity=False).hexdigest()}"'  # noqa: S324

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = f"private, max-age={max_age}"

    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match.strip() == etag:
        raise HTTPException(status_code=304)
