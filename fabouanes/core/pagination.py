from __future__ import annotations

from fabouanes.fastapi_compat import request

from fabouanes.core.db_access import default_page_size, normalize_pagination


def request_pagination() -> tuple[int, int]:
    page_raw = request.args.get("page")
    size_raw = request.args.get("per_page", request.args.get("page_size", default_page_size()))
    try:
        page = int(page_raw) if page_raw is not None and str(page_raw).strip() else 1
    except Exception:
        page = 1
    try:
        page_size = int(size_raw) if size_raw is not None and str(size_raw).strip() else default_page_size()
    except Exception:
        page_size = default_page_size()
    normalized_page, normalized_page_size, _ = normalize_pagination(page, page_size)
    return normalized_page, normalized_page_size
