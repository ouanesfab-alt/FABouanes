"""Tests de couverture ciblés — Lot 5.

Couvre: assistant/sql_tools.py (dry_run_sql, execute_readonly_sql, execute_write_sql, explain_sql_query),
        lifespan.py error branches
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── sql_tools.py (66% → target ~95%) ───────────────────────────────


def test_dry_run_sql_invalid_guard():
    """dry_run_sql returns error message if guard rejects query."""
    from app.modules.assistant.sql_tools import dry_run_sql

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard:
        val = MagicMock()
        val.ok = False
        val.error = "DELETE sans WHERE interdit"
        mock_guard.return_value = val

        res = dry_run_sql("DELETE FROM clients")
        assert "⚠️ Requête SQL refusée" in res


def test_dry_run_sql_execution_success():
    """dry_run_sql runs inside transaction and formats simulation summary."""
    from app.modules.assistant.sql_tools import dry_run_sql

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard, \
         patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:

        val = MagicMock()
        val.ok = True
        val.sql_to_run = "INSERT INTO clients (name) VALUES ('Test')"
        val.statements = None
        mock_guard.return_value = val

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"id": 42}
        mock_cur.rowcount = 1
        mock_conn.execute.return_value = mock_cur
        mock_tx.return_value.__enter__.return_value = mock_conn

        res = dry_run_sql("INSERT INTO clients (name) VALUES ('Test')")
        assert "Simulation" in res
        assert "42" in res or "clients" in res


def test_execute_readonly_sql_rejected():
    """execute_readonly_sql returns error dict if guard rejects query."""
    from app.modules.assistant.sql_tools import execute_readonly_sql

    with patch("app.modules.assistant.sql_tools.guard_readonly_sql") as mock_guard:
        val = MagicMock()
        val.ok = False
        val.error = "Mot-clé DROP interdit"
        mock_guard.return_value = val

        res = execute_readonly_sql("DROP TABLE clients")
        assert "error" in res


def test_execute_readonly_sql_success():
    """execute_readonly_sql returns serialized rows on success."""
    from app.modules.assistant.sql_tools import execute_readonly_sql

    with patch("app.modules.assistant.sql_tools.guard_readonly_sql") as mock_guard, \
         patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:

        val = MagicMock()
        val.ok = True
        val.sql_to_run = "SELECT id, name FROM clients"
        mock_guard.return_value = val

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [{"id": 1, "name": "Alice"}]
        mock_tx.return_value.__enter__.return_value = mock_conn

        res = execute_readonly_sql("SELECT id, name FROM clients")
        assert "rows" in res
        assert res["rows"] == [{"id": 1, "name": "Alice"}]


def test_execute_readonly_sql_timeout():
    """execute_readonly_sql handles statement timeout exception."""
    from app.modules.assistant.sql_tools import execute_readonly_sql

    with patch("app.modules.assistant.sql_tools.guard_readonly_sql") as mock_guard, \
         patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:

        val = MagicMock()
        val.ok = True
        val.sql_to_run = "SELECT * FROM huge_table"
        mock_guard.return_value = val

        mock_tx.return_value.__enter__.side_effect = RuntimeError("statement timeout (57014)")

        res = execute_readonly_sql("SELECT * FROM huge_table")
        assert "error" in res
        assert "10s" in res["error"] or "trop de temps" in res["error"]


def test_execute_write_sql_rejected():
    """execute_write_sql returns error dict if guard rejects query."""
    from app.modules.assistant.sql_tools import execute_write_sql

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard:
        val = MagicMock()
        val.ok = False
        val.error = "Écriture non autorisée"
        mock_guard.return_value = val

        res = execute_write_sql("UPDATE users SET password='123'")
        assert "error" in res


def test_execute_write_sql_success_insert_returning():
    """execute_write_sql with RETURNING handles inserted_id."""
    from app.modules.assistant.sql_tools import execute_write_sql

    with patch("app.modules.assistant.sql_tools.guard_write_sql") as mock_guard, \
         patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:

        val = MagicMock()
        val.ok = True
        val.sql_to_run = "INSERT INTO clients (name) VALUES ('Bob') RETURNING id"
        val.statements = []
        mock_guard.return_value = val

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"id": 100}
        mock_cur.rowcount = 1
        mock_conn.execute.return_value = mock_cur
        mock_tx.return_value.__enter__.return_value = mock_conn

        res = execute_write_sql("INSERT INTO clients (name) VALUES ('Bob') RETURNING id")
        assert res.get("success") is True
        assert res.get("inserted_id") == 100


def test_explain_sql_query():
    """explain_sql_query formats SELECT, INSERT, UPDATE, DELETE queries."""
    from app.modules.assistant.sql_tools import explain_sql_query

    assert explain_sql_query("") == ""

    select_exp = explain_sql_query("SELECT * FROM clients")
    assert "Lecture" in select_exp or "sql" in select_exp

    insert_exp = explain_sql_query("INSERT INTO clients (name) VALUES ('Test')")
    assert "Ajout" in insert_exp or "sql" in insert_exp


# ── lifespan.py exception branches (71% → target ~85%) ──────────────


@pytest.mark.asyncio
async def test_lifespan_exception_handling():
    """Verify lifespan handles sub-system exceptions gracefully during startup and shutdown."""
    from app.core.lifespan import lifespan

    app = MagicMock()

    with patch("app.core.lifespan.validate_single_worker_runtime"), \
         patch("app.core.lifespan.ensure_runtime_dirs"), \
         patch("app.core.lifespan.configure_logging"), \
         patch("app.core.lifespan.start_audit_worker"), \
         patch("app.core.lifespan.stop_audit_worker", side_effect=RuntimeError("Audit stop error")), \
         patch("app.core.lifespan.bootstrap_and_migrate"), \
         patch("app.core.lifespan.get_enabled_modules") as mock_modules:

        mod = MagicMock()
        mod.name = "test_mod"
        mod.schema_sql = ["INVALID SQL STATEMENT"]
        mock_modules.return_value = [mod]

        with patch("app.core.lifespan.execute_db", side_effect=RuntimeError("SQL Error")), \
             patch("app.core.worker.start_worker", side_effect=RuntimeError("Worker start error")), \
             patch("app.core.worker.stop_worker", side_effect=RuntimeError("Worker stop error")), \
             patch("app.services.backup_service.start_background_services"), \
             patch("app.services.backup_service.shutdown_background_services", side_effect=RuntimeError("Backup error")):

            # Lifespan should start and stop cleanly without raising uncaught exceptions
            async with lifespan(app):
                pass
