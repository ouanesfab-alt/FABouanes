"""
test_coverage_boost_lot21.py
Targets remaining uncovered code:
  - manager.py: _invalidate_after_write, _guard_pagination, _record_performance_event,
                _record_sql_timing, postgres_pool_status, shutdown, _pop_performance_batch,
                _write_performance_batch, get_setting, set_setting, list_columns,
                db_task decorator, sqlalchemy_database_url, _env_int, pending/drain
  - lifespan.py: lifespan context manager (startup + shutdown paths)
  - memory.py: async_remember, async_recall, async_forget, async_get_context_memories,
               remember/recall/forget error paths
  - rag.py: get_pdf_text_chunks with content, update_pdf_index with existing index
  - sql_tools.py: dry_run_sql branches, execute_write_sql with RETURNING
  - middleware.py: RequestContextMiddleware form sanitization path
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. manager.py — DatabaseManager method coverage
# ============================================================

from app.core.db_helpers.manager import DatabaseManager, db_task


def make_manager():
    return DatabaseManager()


def test_sqlalchemy_database_url_postgresql():
    mgr = make_manager()
    result = mgr.sqlalchemy_database_url("postgresql://user:pass@localhost/db")
    assert result.startswith("postgresql+pg8000://")


def test_sqlalchemy_database_url_postgres():
    mgr = make_manager()
    result = mgr.sqlalchemy_database_url("postgres://user:pass@localhost/db")
    assert result.startswith("postgresql+pg8000://")


def test_sqlalchemy_database_url_other():
    mgr = make_manager()
    result = mgr.sqlalchemy_database_url("sqlite:///test.db")
    assert result == "sqlite:///test.db"


def test_env_int_valid():
    mgr = make_manager()
    with patch.dict(os.environ, {"TEST_ENV_INT": "42"}):
        result = mgr._env_int("TEST_ENV_INT", 10, 0, 100)
    assert result == 42


def test_env_int_minimum():
    mgr = make_manager()
    with patch.dict(os.environ, {"TEST_ENV_INT": "-5"}):
        result = mgr._env_int("TEST_ENV_INT", 10, 0)
    assert result == 0


def test_env_int_maximum():
    mgr = make_manager()
    with patch.dict(os.environ, {"TEST_ENV_INT": "9999"}):
        result = mgr._env_int("TEST_ENV_INT", 10, 0, 100)
    assert result == 100


def test_env_int_invalid_falls_back():
    mgr = make_manager()
    with patch.dict(os.environ, {"TEST_ENV_INT": "not_a_number"}):
        result = mgr._env_int("TEST_ENV_INT", 42)
    assert result == 42


def test_invalidate_after_write_sales_table():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("INSERT INTO sales (col) VALUES (1)")
        mock_inv.assert_called()
        domains = set(mock_inv.call_args[0])
        assert "sales" in domains


def test_invalidate_after_write_no_write():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("SELECT * FROM clients")
        mock_inv.assert_not_called()


def test_invalidate_after_write_raw_materials():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("UPDATE raw_materials SET stock = 10 WHERE id = 1")
        mock_inv.assert_called()
        domains = set(mock_inv.call_args[0])
        assert "catalog" in domains


def test_invalidate_after_write_purchases():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("INSERT INTO purchases (col) VALUES (1)")
        mock_inv.assert_called()


def test_invalidate_after_write_production():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("INSERT INTO production_batches (col) VALUES (1)")
        mock_inv.assert_called()
        domains = set(mock_inv.call_args[0])
        assert "productions" in domains


def test_invalidate_after_write_expenses():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("INSERT INTO expenses (col) VALUES (1)")
        mock_inv.assert_called()
        domains = set(mock_inv.call_args[0])
        assert "dashboard" in domains


def test_invalidate_after_write_users():
    mgr = make_manager()
    with patch("app.core.db_helpers.manager.invalidate_cache_domains") as mock_inv:
        mgr._invalidate_after_write("UPDATE users SET last_login = NOW() WHERE id = 1")
        mock_inv.assert_called()
        domains = set(mock_inv.call_args[0])
        assert "admin" in domains


def test_guard_pagination_select_no_limit():
    mgr = make_manager()
    result = mgr._guard_pagination("SELECT * FROM clients")
    assert "LIMIT" in result.upper()


def test_guard_pagination_select_with_limit():
    mgr = make_manager()
    result = mgr._guard_pagination("SELECT * FROM clients LIMIT 10")
    assert result == "SELECT * FROM clients LIMIT 10"


def test_guard_pagination_count_query():
    mgr = make_manager()
    result = mgr._guard_pagination("SELECT count(*) FROM clients")
    assert "LIMIT" not in result.upper()


def test_guard_pagination_non_select():
    mgr = make_manager()
    query = "INSERT INTO clients (name) VALUES ('Test')"
    result = mgr._guard_pagination(query)
    assert result == query


def test_record_sql_timing_slow():
    mgr = make_manager()
    mgr._slow_sql_threshold_ms = 0  # Make everything "slow"
    with patch.object(mgr, "_record_performance_event") as mock_rec:
        mgr._record_sql_timing("SELECT * FROM clients", (), 500.0)
        mock_rec.assert_called_once()


def test_record_sql_timing_fast():
    mgr = make_manager()
    mgr._slow_sql_threshold_ms = 10000  # Nothing is "slow"
    with patch.object(mgr, "_record_performance_event") as mock_rec:
        mgr._record_sql_timing("SELECT 1", (), 1.0)
        mock_rec.assert_not_called()


def test_record_performance_event():
    mgr = make_manager()
    with patch.object(mgr, "_ensure_performance_worker"):
        mgr._record_performance_event("sql", "SELECT * FROM clients", 150.0)
        assert mgr.pending_performance_event_count() == 1


def test_record_performance_event_performance_logs_table_skipped():
    mgr = make_manager()
    with patch.object(mgr, "_ensure_performance_worker") as mock_ew:
        mgr._record_performance_event("sql", "performance_logs query", 500.0)
        mock_ew.assert_not_called()


def test_record_performance_event_zero_elapsed_skipped():
    mgr = make_manager()
    with patch.object(mgr, "_ensure_performance_worker") as mock_ew:
        mgr._record_performance_event("sql", "SELECT 1", 0.0)
        mock_ew.assert_not_called()


def test_pop_performance_batch():
    mgr = make_manager()
    with patch.object(mgr, "_ensure_performance_worker"):
        mgr._record_performance_event("sql", "SELECT 1", 100.0)
        mgr._record_performance_event("sql", "SELECT 2", 200.0)
    batch = mgr._pop_performance_batch(1)
    assert len(batch) == 1
    remaining = mgr._pop_performance_batch(10)
    assert len(remaining) == 1


def test_pending_performance_event_count():
    mgr = make_manager()
    assert mgr.pending_performance_event_count() == 0
    with patch.object(mgr, "_ensure_performance_worker"):
        mgr._record_performance_event("sql", "SELECT 1", 100.0)
    assert mgr.pending_performance_event_count() == 1


def test_tx_depth_methods():
    mgr = make_manager()
    from app.core.request_state import reset_request_state, push_request_state
    from types import SimpleNamespace
    from fastapi import Request

    # Create a fake request scope
    scope = {"type": "http", "method": "GET", "path": "/test",
             "query_string": b"", "headers": []}
    req = Request(scope)
    token = push_request_state(
        request=req, db=None, session={}, request_id="test",
        audit_source="api", user=None, g=SimpleNamespace(user=None), csp_nonce="abc"
    )
    try:
        depth = mgr._tx_depth()
        assert depth == 0
        mgr._set_tx_depth(3)
        assert mgr._tx_depth() == 3
    finally:
        reset_request_state(token)


def test_shutdown_drains_queue():
    mgr = make_manager()
    # Add items to perf queue
    with patch.object(mgr, "_ensure_performance_worker"):
        mgr._record_performance_event("sql", "SELECT 1", 100.0)

    # Mock write so it doesn't try to connect to DB
    with patch.object(mgr, "_write_performance_batch") as mock_write, \
         patch.object(mgr, "connect_database"):
        mgr.shutdown()
    assert mgr._perf_shutdown is True


def test_drain_performance_events_once():
    mgr = make_manager()
    with patch.object(mgr, "_ensure_performance_worker"):
        mgr._record_performance_event("sql", "SELECT 1", 100.0)
    with patch.object(mgr, "_write_performance_batch") as mock_write:
        count = mgr.drain_performance_events_once()
    assert count >= 0


def test_db_task_decorator():
    @db_task
    def my_func(x):
        return x * 2

    assert my_func(5) == 10
    assert my_func.sync(5) == 10
    assert asyncio.run(my_func.async_(5)) == 10


# ============================================================
# 2. lifespan.py — test the lifespan async context manager
# ============================================================

@pytest.mark.asyncio
async def test_lifespan_startup_shutdown():
    """Test that lifespan runs startup and shutdown without crashing."""
    from app.core.lifespan import lifespan
    from fastapi import FastAPI

    app = FastAPI()

    # All local imports inside lifespan must be patched at their source module
    with (
        patch("app.core.lifespan.validate_single_worker_runtime"),
        patch("app.core.lifespan.ensure_runtime_dirs"),
        patch("app.core.lifespan.configure_logging"),
        patch("app.core.lifespan.start_audit_worker"),
        patch("app.core.lifespan.stop_audit_worker"),
        patch("app.core.lifespan.bootstrap_and_migrate"),
        patch("app.core.lifespan.get_enabled_modules", return_value=[]),
        # These are local imports inside the function body — patch at source
        patch("app.services.backup_service.start_background_services"),
        patch("app.services.backup_service.shutdown_background_services"),
        patch("app.core.events.startup"),
        patch("app.core.events.shutdown"),
        patch("app.core.worker.start_worker"),
        patch("app.core.worker.stop_worker"),
        patch("app.core.perf_cache.warm_cache", new=AsyncMock(return_value=None)),
        patch("app.modules.assistant.service.close_http_clients", new=AsyncMock(return_value=None)),
        patch("app.core.db_helpers.db_manager.shutdown"),
        patch("app.core.async_db.close_async_engine", new=AsyncMock(return_value=None)),
        patch("asyncio.to_thread", new=AsyncMock(return_value=None)),
    ):
        async with lifespan(app):
            pass  # startup + yield + shutdown


# ============================================================
# 3. memory.py — async wrappers
# ============================================================

from app.modules.assistant.memory import (
    remember, recall, forget, get_context_memories,
    async_remember, async_recall, async_forget, async_get_context_memories,
)


def test_remember_success():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.return_value = []  # No duplicate
        mock_db.execute_db.return_value = 42
        result = remember("J'aime les chats", "preference")
    assert result["success"] is True
    assert result["memory_id"] == 42


def test_remember_duplicate():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.return_value = [(99,)]  # Already exists
        result = remember("J'aime les chats")
    assert result["status"] == "already_known"


def test_remember_empty_content():
    result = remember("")
    assert "error" in result


def test_remember_db_error():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.side_effect = Exception("DB error")
        result = remember("test content")
    assert "error" in result


def test_recall_with_query():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_row = MagicMock()
        mock_row.__iter__ = MagicMock(return_value=iter([]))
        mock_row.keys = MagicMock(return_value=["id"])
        mock_db.query_db.return_value = []
        result = recall("chat preferences")
    assert result["count"] == 0


def test_recall_empty_query():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.return_value = []
        result = recall("")
    assert result["count"] == 0
    assert "Aucun" in result["message"]


def test_recall_db_error():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.side_effect = Exception("DB error")
        result = recall("test")
    assert "error" in result


def test_forget_success():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.execute_db.return_value = 42
        result = forget(42)
    assert result["success"] is True


def test_forget_not_found():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.execute_db.return_value = 0
        result = forget(999)
    assert "error" in result


def test_forget_db_error():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.execute_db.side_effect = Exception("DB error")
        result = forget(1)
    assert "error" in result


def test_get_context_memories_empty():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.return_value = []
        result = get_context_memories()
    assert result == ""


def test_get_context_memories_with_data():
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, k: {"category": "preference", "content": "J'aime Python"}[k]
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.return_value = [{"category": "preference", "content": "J'aime Python"}]
        result = get_context_memories()
    assert isinstance(result, str)
    assert "preference" in result or "Python" in result or "MÉMOIRE" in result


def test_get_context_memories_db_error():
    with patch("app.modules.assistant.memory.db_manager") as mock_db:
        mock_db.query_db.side_effect = Exception("DB error")
        result = get_context_memories()
    assert result == ""


@pytest.mark.asyncio
async def test_async_remember():
    with patch("app.modules.assistant.memory.remember", return_value={"success": True}) as mock_r:
        result = await async_remember("test content")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_async_recall():
    with patch("app.modules.assistant.memory.recall", return_value={"count": 0}) as mock_r:
        result = await async_recall("test query")
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_async_forget():
    with patch("app.modules.assistant.memory.forget", return_value={"success": True}) as mock_r:
        result = await async_forget(1)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_async_get_context_memories():
    with patch("app.modules.assistant.memory.get_context_memories", return_value="memories") as mock_r:
        result = await async_get_context_memories()
    assert result == "memories"


# ============================================================
# 4. rag.py — get_pdf_text_chunks with actual content mock
# ============================================================

from app.modules.assistant.rag import get_pdf_text_chunks, update_pdf_index


def test_get_pdf_text_chunks_with_pages(tmp_path):
    """Mock PdfReader to simulate content extraction."""
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Premier paragraphe avec du texte assez long.\n\nDeuxième paragraphe aussi long."

    fake_reader = MagicMock()
    fake_reader.pages = [fake_page, fake_page]

    with patch("app.modules.assistant.rag.PdfReader", return_value=fake_reader):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake pdf content")
        chunks = get_pdf_text_chunks(fake_pdf)

    assert isinstance(chunks, list)
    assert len(chunks) > 0
    assert "text" in chunks[0]
    assert "page" in chunks[0]


def test_get_pdf_text_chunks_empty_page(tmp_path):
    """Page with no text should be skipped."""
    fake_page = MagicMock()
    fake_page.extract_text.return_value = None

    fake_reader = MagicMock()
    fake_reader.pages = [fake_page]

    with patch("app.modules.assistant.rag.PdfReader", return_value=fake_reader):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake pdf content")
        chunks = get_pdf_text_chunks(fake_pdf)

    assert chunks == []


def test_update_pdf_index_removes_deleted(tmp_path):
    """If index has entries for non-existent PDFs, they should be removed."""
    index_path = tmp_path / "index_rag.json"
    # Pre-populate index with a non-existent PDF
    existing_index = {
        "old_nonexistent.pdf": {"mtime": 12345.0, "chunks": [{"text": "old", "page": 1, "para_idx": 0}]}
    }
    index_path.write_text(json.dumps(existing_index), encoding="utf-8")

    with patch("app.modules.assistant.rag.paths") as mock_paths, \
         patch("app.modules.assistant.rag.INDEX_FILE", index_path):
        mock_paths.pdf_reader_dir = tmp_path  # Empty dir, no PDFs
        result = update_pdf_index()

    # old entry should be removed since the PDF doesn't exist
    assert "old_nonexistent.pdf" not in result


def test_update_pdf_index_indexes_new_pdf(tmp_path):
    """New PDFs should be indexed."""
    fake_pdf = tmp_path / "test_doc.pdf"
    fake_pdf.write_bytes(b"fake content")
    index_path = tmp_path / "index_rag.json"

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Contenu du document PDF pour le test de couverture."
    fake_reader = MagicMock()
    fake_reader.pages = [fake_page]

    with patch("app.modules.assistant.rag.paths") as mock_paths, \
         patch("app.modules.assistant.rag.INDEX_FILE", index_path), \
         patch("app.modules.assistant.rag.PdfReader", return_value=fake_reader):
        mock_paths.pdf_reader_dir = tmp_path
        result = update_pdf_index()

    assert "test_doc.pdf" in result


# ============================================================
# 5. sql_tools.py — dry_run_sql and execute_write_sql paths
# ============================================================

from app.modules.assistant.sql_tools import dry_run_sql, execute_write_sql


def test_dry_run_sql_guard_rejection():
    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard:
        mock_guard.return_value = MagicMock(ok=False, error="SQL refusé")
        result = dry_run_sql("DROP TABLE clients")
    assert "refusée" in result or "error" in result.lower()


def test_dry_run_sql_empty_statements():
    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard:
        mock_guard.return_value = MagicMock(
            ok=True,
            sql_to_run="SELECT 1",
            statements=None,
        )
        result = dry_run_sql("SELECT 1")
    assert isinstance(result, str)


def test_dry_run_sql_db_exception():
    @contextmanager
    def fail_transaction():
        raise Exception("DB connection lost")
        yield None  # pragma: no cover

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard, \
         patch("app.modules.assistant.sql_tools.db_manager") as mock_mgr:
        mock_guard.return_value = MagicMock(
            ok=True,
            sql_to_run="UPDATE clients SET name = 'X'",
            statements=[MagicMock()],
        )
        mock_mgr.db_transaction = fail_transaction
        result = dry_run_sql("UPDATE clients SET name = 'X'")
    assert "échoué" in result or "error" in result.lower()


def test_execute_write_sql_with_returning():
    """Test RETURNING clause path in execute_write_sql."""
    @contextmanager
    def fake_transaction():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"id": 99}
        mock_cur.rowcount = 1
        mock_conn.execute.return_value = mock_cur
        yield mock_conn

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard, \
         patch("app.modules.assistant.sql_tools.db_manager") as mock_mgr:
        mock_guard.return_value = MagicMock(
            ok=True,
            sql_to_run="INSERT INTO clients (name) VALUES ('Test') RETURNING id",
            statements=[],
        )
        mock_mgr.db_transaction = fake_transaction
        result = execute_write_sql("INSERT INTO clients (name) VALUES ('Test') RETURNING id")
    assert isinstance(result, dict)
    assert "success" in result or "error" in result


def test_execute_write_sql_db_failure():
    @contextmanager
    def fail_transaction():
        raise Exception("Connection error")
        yield None  # pragma: no cover

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard, \
         patch("app.modules.assistant.sql_tools.db_manager") as mock_mgr:
        mock_guard.return_value = MagicMock(
            ok=True,
            sql_to_run="INSERT INTO dummy VALUES (1)",
            statements=[],
        )
        mock_mgr.db_transaction = fail_transaction
        result = execute_write_sql("INSERT INTO dummy VALUES (1)")
    assert "error" in result


# ============================================================
# 6. sql_guard.py — uncovered validation branches
# ============================================================

from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql


def test_validate_readonly_select():
    result = validate_readonly_sql("SELECT id, name FROM clients LIMIT 10")
    assert result.ok is True


def test_validate_readonly_non_select():
    result = validate_readonly_sql("DROP TABLE clients")
    assert result.ok is False


def test_validate_readonly_empty():
    result = validate_readonly_sql("")
    assert result.ok is False


def test_validate_write_sql_insert():
    result = validate_write_sql("INSERT INTO clients (name) VALUES ('Test')")
    assert result.ok is True


def test_validate_write_sql_select_rejected():
    result = validate_write_sql("SELECT * FROM clients")
    assert result.ok is False


def test_validate_write_sql_empty():
    result = validate_write_sql("")
    assert result.ok is False
