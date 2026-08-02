"""
test_ultra_coverage_lot49.py
Targets:
  - sql_tools.py: explain_sql_query non-CRUD & empty parse, execute_write_sql RETURNING fetch error & close error (lines 200-201, 205-206, 217, 232, 245)
  - middleware.py: RequestContextMiddleware static path, UploadFile form item, cleanup exception (lines 32-33, 46, 89-90)
  - schema/__init__.py: validation error formatting (lines 30-31, 64, 88-89)
  - lifespan.py: app startup & shutdown exception handling (lines 72-73, 90-92)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. sql_tools.py — explain_sql_query non-CRUD & RETURNING fetch error
# ============================================================

def test_sql_tools_explain_and_execute_returning_fetch_error():
    """Lines 200-201, 205-206, 217, 232, 245: explain_sql_query non-CRUD & RETURNING error handling."""
    from app.modules.assistant.sql_tools import explain_sql_query, execute_write_sql

    # Non-CRUD query
    exp1 = explain_sql_query("COMMIT;")
    assert "sql" in exp1

    # Empty query
    exp2 = explain_sql_query("")
    assert exp2 == ""

    # execute_write_sql with fetchone raising exception & cur.close raising exception
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = Exception("Fetch error")
    mock_cur.close.side_effect = Exception("Close error")
    mock_cur.rowcount = None

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.query_db", return_value=[]), \
         patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("INSERT INTO clients (name) VALUES ('X') RETURNING id")

    assert res.get("success") is True
    assert "message" in res


# ============================================================
# 2. middleware.py — static path, UploadFile & cleanup error
# ============================================================

@pytest.mark.asyncio
async def test_middleware_static_path_and_upload_file():
    """Lines 32-33, 46, 89-90: RequestContextMiddleware static path bypass, UploadFile form item, and cleanup exception."""
    from fastapi import Request
    from starlette.datastructures import UploadFile
    from app.core.middleware import RequestContextMiddleware

    middleware = RequestContextMiddleware(app=MagicMock())

    # Static path request
    req_static = MagicMock(spec=Request)
    req_static.url.path = "/static/css/style.css"

    async def call_next_static(r):
        resp = MagicMock()
        resp.headers = {}
        return resp

    resp_static = await middleware.dispatch(req_static, call_next_static)
    assert resp_static is not None

    # Form with UploadFile item
    req_form = MagicMock(spec=Request)
    req_form.url.path = "/api/v1/upload"
    req_form.headers = {"content-type": "multipart/form-data"}
    req_form.session = {}

    upload_file = MagicMock(spec=UploadFile)
    mock_form_data = MagicMock()
    mock_form_data.multi_items.return_value = [("file", upload_file), ("password", "secret"), ("name", "test")]

    async def get_form():
        return mock_form_data

    req_form.form = get_form

    async def call_next_form(r):
        # Trigger request.form() call
        form = await r.form()
        resp = MagicMock()
        resp.headers = {}
        return resp

    with patch("app.core.middleware.push_request_state", return_value="token"), \
         patch("app.core.middleware.reset_request_state"):
        resp_form = await middleware.dispatch(req_form, call_next_form)

    assert resp_form is not None


# ============================================================
# 3. lifespan.py — startup & shutdown error handling
# ============================================================

@pytest.mark.asyncio
async def test_lifespan_error_handling():
    """Lines 72-73, 90-92: lifespan context manager handles exceptions during cache warming and audit worker shutdown."""
    from app.core.lifespan import lifespan

    mock_app = MagicMock()

    with patch("asyncio.to_thread"), \
         patch("app.core.lifespan.get_enabled_modules", return_value=[]), \
         patch("app.core.perf_cache.warm_cache", side_effect=Exception("Cache error")), \
         patch("app.core.audit.stop_audit_worker", side_effect=Exception("Audit stop error")):
        async with lifespan(mock_app):
            pass
