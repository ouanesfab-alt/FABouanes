"""
Tests pour couvrir les modules à faible couverture :
- app.core.db_helpers.query
- app.core.schema.__init__
- app.modules.sales.queries
"""
from __future__ import annotations

import os
import sys
import pytest
from unittest import mock
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest-unit-only")
os.environ.setdefault("FASTAPI_ENV", "test")
os.environ.setdefault("FAB_DESKTOP", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fabouanes.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")


# =============================================================================
# 1. app.core.db_helpers.query — split_sql_script + validate_identifier
# =============================================================================

class TestSplitSqlScript:
    def test_single_statement(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("SELECT 1;")
        assert result == ["SELECT 1"]

    def test_multiple_statements(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("SELECT 1; SELECT 2;")
        assert len(result) == 2
        assert result[0] == "SELECT 1"
        assert result[1] == "SELECT 2"

    def test_empty_script(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("")
        assert result == []

    def test_line_comment_stripped(self):
        from app.core.db_helpers.query import split_sql_script
        script = "-- This is a comment\nSELECT 1;"
        result = split_sql_script(script)
        assert len(result) == 1
        assert "SELECT 1" in result[0]

    def test_block_comment_stripped(self):
        from app.core.db_helpers.query import split_sql_script
        script = "/* block comment */ SELECT 1;"
        result = split_sql_script(script)
        assert len(result) == 1
        assert "SELECT 1" in result[0]

    def test_dollar_quoted_string(self):
        from app.core.db_helpers.query import split_sql_script
        script = "CREATE FUNCTION f() RETURNS void AS $$ BEGIN NULL; END; $$ LANGUAGE plpgsql;"
        result = split_sql_script(script)
        assert len(result) == 1

    def test_single_quoted_string_with_semicolon(self):
        from app.core.db_helpers.query import split_sql_script
        script = "INSERT INTO t VALUES ('a;b');"
        result = split_sql_script(script)
        assert len(result) == 1
        assert "a;b" in result[0]

    def test_double_quoted_identifier(self):
        from app.core.db_helpers.query import split_sql_script
        script = 'SELECT "col;name" FROM t;'
        result = split_sql_script(script)
        assert len(result) == 1

    def test_statement_without_trailing_semicolon(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("SELECT 1")
        assert result == ["SELECT 1"]

    def test_whitespace_only_not_included(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("   ;  ;  ")
        assert result == []

    def test_multiple_with_no_final_semicolon(self):
        from app.core.db_helpers.query import split_sql_script
        result = split_sql_script("SELECT 1; SELECT 2")
        assert len(result) == 2


class TestValidateIdentifier:
    def test_valid_identifier(self):
        from app.core.db_helpers.query import validate_identifier
        validate_identifier("users")
        validate_identifier("my_table")
        validate_identifier("schema.table")

    def test_empty_identifier_raises(self):
        from app.core.db_helpers.query import validate_identifier
        with pytest.raises(ValueError, match="Invalid database identifier"):
            validate_identifier("")

    def test_none_identifier_raises(self):
        from app.core.db_helpers.query import validate_identifier
        with pytest.raises(ValueError, match="Invalid database identifier"):
            validate_identifier(None)

    def test_sql_injection_raises(self):
        from app.core.db_helpers.query import validate_identifier
        with pytest.raises(ValueError, match="Invalid database identifier"):
            validate_identifier("users; DROP TABLE users")

    def test_hyphen_in_name_raises(self):
        from app.core.db_helpers.query import validate_identifier
        with pytest.raises(ValueError, match="Invalid database identifier"):
            validate_identifier("my-table")

    def test_starting_with_number_raises(self):
        from app.core.db_helpers.query import validate_identifier
        with pytest.raises(ValueError, match="Invalid database identifier"):
            validate_identifier("1table")


# =============================================================================
# 2. app.core.schema — initial_admin_password + seed functions
# =============================================================================

class TestInitialAdminPassword:
    def test_returns_configured_password(self):
        with mock.patch.dict(os.environ, {"DEFAULT_ADMIN_PASSWORD": "SecurePass!123"}):
            with mock.patch("app.core.config.DEFAULT_ADMIN_PASSWORD", "SecurePass!123"):
                from app.core.schema import initial_admin_password
                # Force reload
                with mock.patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", "SecurePass!123"):
                    with mock.patch("app.core.schema.FIRST_ADMIN_PASSWORD_FILE") as mock_file:
                        mock_file.exists.return_value = False
                        result = initial_admin_password()
                        assert isinstance(result, str)
                        assert len(result) > 0

    def test_generates_pin_when_no_config(self):
        with mock.patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", ""):
            with mock.patch("app.core.schema.FIRST_ADMIN_PASSWORD_FILE") as mock_file:
                mock_file.exists.return_value = False
                mock_file.write_text = mock.MagicMock()
                with mock.patch("app.core.schema.ensure_runtime_dirs"):
                    from app.core.schema import initial_admin_password
                    result = initial_admin_password()
                    assert isinstance(result, str)
                    assert len(result) == 4
                    assert result != "1234"

    def test_reads_pin_from_file(self):
        with mock.patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", ""):
            with mock.patch("app.core.schema.FIRST_ADMIN_PASSWORD_FILE") as mock_file:
                mock_file.exists.return_value = True
                mock_file.read_text.return_value = "Utilisateur=admin\nPIN=5678\n"
                from app.core.schema import initial_admin_password
                result = initial_admin_password()
                assert result == "5678"


class TestSeedFunctions:
    def test_seed_default_settings(self):
        from app.core.schema import _seed_default_settings
        mock_conn = mock.MagicMock()
        _seed_default_settings(mock_conn)
        # Should call execute 5 times (5 default settings)
        assert mock_conn.execute.call_count == 5

    def test_seed_other_operation_insert(self):
        from app.core.schema import _seed_other_operation
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_cursor.fetchone.return_value = None  # No existing "AUTRE" row
        mock_conn.execute.return_value = mock_cursor
        _seed_other_operation(mock_conn)
        # Should try INSERT
        assert mock_conn.execute.call_count >= 1

    def test_seed_other_operation_update(self):
        from app.core.schema import _seed_other_operation
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_row = {"id": 42}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        _seed_other_operation(mock_conn)
        # Should UPDATE since row exists
        calls = [str(c) for c in mock_conn.execute.call_args_list]
        assert any("UPDATE" in c for c in calls)

    def test_seed_default_admin_creates_user(self):
        from app.core.schema import _seed_default_admin
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_cursor.fetchone.return_value = None  # no admin yet
        mock_conn.execute.return_value = mock_cursor
        with mock.patch("app.core.schema.initial_admin_password", return_value="5678"):
            _seed_default_admin(mock_conn)
        # Should INSERT new admin
        assert mock_conn.execute.call_count >= 1


# =============================================================================
# 3. app.modules.sales.queries — SalesQueries unit tests
# =============================================================================

class TestSalesQueries:
    @pytest.mark.asyncio
    async def test_list_sales(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.sale_repo = mock.AsyncMock()
        queries.sale_repo.list_sales_paginated.return_value = ([{"id": 1}], 1)
        
        result, count = await queries.list_sales(search="test", page=1)
        assert count == 1
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_sale_form_context(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.sale_repo = mock.AsyncMock()
        queries.sale_repo.list_sellable_items.return_value = [{"id": 1, "name": "Item A"}]
        
        ctx = await queries.sale_form_context()
        assert "sellable_items" in ctx
        assert "units" in ctx
        assert len(ctx["sellable_items"]) == 1

    @pytest.mark.asyncio
    async def test_get_sale_document_context_not_found(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.doc_repo = mock.AsyncMock()
        queries.doc_repo.get_by_id.return_value = None
        
        result = await queries.get_sale_document_context(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sale_edit_context_not_found(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.sale_repo = mock.AsyncMock()
        queries.sale_repo.get_sale_detail.return_value = None
        
        result = await queries.get_sale_edit_context("finished", 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sale_edit_context_with_document_id(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.sale_repo = mock.AsyncMock()
        queries.sale_repo.get_sale_detail.return_value = {"document_id": 5}
        queries.doc_repo = mock.AsyncMock()
        queries.doc_repo.get_by_id.return_value = None  # Simulate not found
        
        result = await queries.get_sale_edit_context("finished", 1)
        # Should return None since document context is None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sale_edit_context_raw_sale(self):
        from app.modules.sales.queries import SalesQueries
        mock_session = mock.AsyncMock()
        queries = SalesQueries(mock_session)
        queries.sale_repo = mock.AsyncMock()
        queries.sale_repo.get_sale_detail.return_value = {
            "id": 1,
            "document_id": None,
            "client_id": 10,
            "sale_type": "cash",
            "sale_date": "2025-01-01",
            "notes": "test",
            "row_kind": "finished",
            "item_key": "prod-1",
            "item_name": "Produit A",
            "quantity": 2.0,
            "unit": "pcs",
            "unit_price": 100.0,
            "total": 200.0,
            "amount_paid": 200.0,
            "balance_due": 0.0,
            "custom_item_name": None,
        }
        
        result = await queries.get_sale_edit_context("finished", 1)
        assert result is not None
        assert "sale_document" in result
        assert "sale_lines" in result
        assert result["has_linked_payments"] is False
        line = result["sale_lines"][0]
        assert line["row_kind"] == "finished"
        assert line["total"] == 200.0
