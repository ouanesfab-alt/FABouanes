import pytest
from unittest.mock import patch, AsyncMock
from app.modules.assistant.service import (
    run_assistant_agent,
    compress_history_if_needed,
)
from app.modules.assistant.sql_tools import execute_readonly_sql, dry_run_sql
from app.modules.assistant.tool_actions import execute_tool_action, sanitize_numeric
from app.modules.assistant.tool_specs import get_gemini_tools, get_ollama_tools
from app.modules.assistant.confirmations import tool_requires_confirmation
from app.core.sanitizer import sanitize_string, MAX_INPUT_LENGTH

def test_execute_readonly_sql_validation():
    # Test queries that should fail basic read-only validation
    res = execute_readonly_sql("INSERT INTO clients (name) VALUES ('test')")
    assert "error" in res
    assert "interdite" in res["error"]

    res_update = execute_readonly_sql("UPDATE clients SET name = 'test'")
    assert "error" in res_update
    assert "interdite" in res_update["error"]

    res_injection = execute_readonly_sql("SELECT * FROM clients; DROP TABLE clients;")
    assert "error" in res_injection
    assert "Une seule requête" in res_injection["error"] or "interdite" in res_injection["error"] or "syntaxe" in res_injection["error"]

def test_sql_guard_adds_read_limit_and_blocks_users_table():
    from app.modules.assistant.sql_guard import validate_readonly_sql

    valid = validate_readonly_sql("SELECT id, name FROM clients")
    assert valid.ok is True
    assert valid.sql_to_run is not None
    assert "LIMIT 100" in valid.sql_to_run.upper()

    protected = validate_readonly_sql("SELECT id, username FROM users")
    assert protected.ok is False
    assert "protegee" in protected.error

    protected_settings = validate_readonly_sql("SELECT key, value FROM app_settings")
    assert protected_settings.ok is False
    assert "protegee" in protected_settings.error


def test_execute_write_sql_blocks_unsafe_queries():
    from app.modules.assistant.service import execute_write_sql

    multi = execute_write_sql("INSERT INTO clients (name) VALUES ('A'); UPDATE clients SET notes = 'x' WHERE name = 'A'")
    assert "error" in multi
    assert "SQL d'" in multi["error"]

    ddl = execute_write_sql("DROP TABLE clients")
    assert "error" in ddl
    assert "INSERT, UPDATE et DELETE" in ddl["error"] or "structure" in ddl["error"]

    read = execute_write_sql("SELECT * FROM clients")
    assert "error" in read
    assert "INSERT, UPDATE et DELETE" in read["error"]

    protected = execute_write_sql("UPDATE users SET role = 'admin' WHERE id = 1")
    assert "error" in protected
    assert "protegee" in protected["error"]

    protected_settings = execute_write_sql("UPDATE app_settings SET value = 'x' WHERE key = 'gemini_api_key'")
    assert "error" in protected_settings
    assert "protegee" in protected_settings["error"]


def test_sanitizer_truncation():
    # Test that normal strings are not truncated
    normal_str = "A Normal String"
    assert sanitize_string(normal_str) == "A Normal String"

    # Test that excessively long strings are truncated at MAX_INPUT_LENGTH
    long_str = "x" * (MAX_INPUT_LENGTH + 10)
    sanitized = sanitize_string(long_str)
    assert len(sanitized) > MAX_INPUT_LENGTH
    assert "[TRUNCATED]" in sanitized
    assert sanitized.startswith("x" * MAX_INPUT_LENGTH)

@pytest.mark.asyncio
async def test_run_assistant_agent_no_tool_call():
    # Mock call_gemini_api to return a simple text response
    mock_response = {
        "candidates": [{
            "content": {
                "role": "model",
                "parts": [{"text": "Bonjour ! Comment puis-je vous aider ?"}]
            }
        }]
    }

    with patch("app.modules.assistant.service.call_gemini_api", new_callable=AsyncMock) as mock_call:
        with patch("app.core.db_helpers.db_manager.get_setting", return_value="gemini-3.1-flash-lite"):
            mock_call.return_value = mock_response
            result = await run_assistant_agent([], "fake_api_key")
            assert result == "Bonjour ! Comment puis-je vous aider ?"
            mock_call.assert_called_once()

def test_dry_run_sql_preview():
    # Verify that dry run for modification queries compiles and displays simulation info
    res = dry_run_sql("UPDATE clients SET notes = 'test' WHERE id = 99999")
    assert "Simulation" in res or "dry-run" in res


def test_dry_run_sql_uses_write_guard():
    with patch("app.core.db_helpers.db_manager.db_transaction") as mock_tx:
        res = dry_run_sql("DROP TABLE clients")
        assert "refus" in res.lower()
        mock_tx.assert_not_called()

@pytest.mark.asyncio
async def test_read_app_file_security():
    # Verify path traversal / base dir escape protection
    res = await execute_tool_action("read_app_file", {"filepath": "c:/windows/system32/cmd.exe"})
    assert "error" in res
    assert "Sécurité" in res["error"]

    res_ok = await execute_tool_action("read_app_file", {"filepath": "app/modules/assistant/service.py"})
    assert "error" not in res_ok
    assert "content" in res_ok

@pytest.mark.asyncio
async def test_compress_history_if_needed():
    # Verify sliding memory window compression returns a summary prefix
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Résumé condensé de la conversation"}]
            }
        }]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        msgs = [{"role": "user", "parts": [{"text": f"Message {i}"}]} for i in range(20)]
        compressed = await compress_history_if_needed(msgs, "fake_key", is_local=False)
        assert len(compressed) <= 9
        assert "[CONTEXTE" in compressed[0]["parts"][0]["text"]
        mock_post.assert_called_once()

def test_get_ollama_tools():
    # Verify local tool specs dynamically convert JSON Schema types to lowercase for Ollama compatibility
    tools = get_ollama_tools()
    assert len(tools) > 0
    for t in tools:
        assert t["type"] == "function"
        params = t["function"].get("parameters", {})
        if "properties" in params:
            for prop in params["properties"].values():
                assert "type" in prop
                assert prop["type"].islower()


def test_tool_confirmation_policy_is_centralized():
    assert tool_requires_confirmation("search_clients") is False
    assert tool_requires_confirmation("remember") is False
    assert tool_requires_confirmation("add_sale") is True
    assert tool_requires_confirmation("save_user_note") is True


def test_product_tool_schema_exposes_stock_fields():
    declarations = get_gemini_tools()[0]["functionDeclarations"]
    by_name = {tool["name"]: tool for tool in declarations}

    add_props = by_name["add_product"]["parameters"]["properties"]
    assert "stock_qty" in add_props
    assert "alert_threshold" in add_props

    modify_props = by_name["modify_product"]["parameters"]["properties"]
    assert "unit" in modify_props
    assert "stock_qty" in modify_props
    assert "alert_threshold" in modify_props


def test_supplier_tool_schema_exposes_crud_tools():
    declarations = get_gemini_tools()[0]["functionDeclarations"]
    by_name = {tool["name"]: tool for tool in declarations}

    assert {"add_supplier", "modify_supplier", "delete_supplier"}.issubset(by_name)
    assert "name" in by_name["add_supplier"]["parameters"]["properties"]
    assert "supplier_id" in by_name["modify_supplier"]["parameters"]["properties"]
    assert "supplier_id" in by_name["delete_supplier"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_supplier_tools_use_contact_service():
    from unittest.mock import MagicMock

    fake_session = AsyncMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    fake_session_maker = MagicMock(return_value=fake_cm)

    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        with patch("app.services.contact_directory_service.create_supplier_from_form", new_callable=AsyncMock, return_value=77) as mock_create:
            res = await execute_tool_action("add_supplier", {"name": "acme", "phone": "0555"})
            assert res["success"] is True
            assert res["supplier_id"] == 77
            mock_create.assert_awaited_once()
            fake_session.commit.assert_awaited()

    fake_session.commit.reset_mock()
    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        with patch("app.services.contact_directory_service.get_supplier", new_callable=AsyncMock, return_value={"id": 77, "name": "Acme", "phone": "", "address": "", "notes": ""}):
            with patch("app.services.contact_directory_service.update_supplier_from_form", new_callable=AsyncMock) as mock_update:
                res = await execute_tool_action("modify_supplier", {"supplier_id": 77, "notes": "ok"})
                assert res["success"] is True
                mock_update.assert_awaited_once()
                fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_commercial_tools_use_business_services():
    from unittest.mock import MagicMock

    fake_session = AsyncMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    fake_session_maker = MagicMock(return_value=fake_cm)

    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        sale_service = MagicMock()
        sale_service.create_sale_from_form = AsyncMock(return_value={"print_item_id": 11})
        with patch("app.modules.sales.service.SalesService", return_value=sale_service):
            res = await execute_tool_action(
                "add_sale",
                {"item_kind": "finished", "item_id": 1, "quantity": 2, "unit": "kg", "unit_price": 50},
            )
            assert res["success"] is True
            assert res["sale_id"] == 11
            sale_service.create_sale_from_form.assert_awaited_once()
            fake_session.commit.assert_awaited()

    fake_session.commit.reset_mock()
    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        purchase_service = MagicMock()
        purchase_service.create_purchase_from_form = AsyncMock(return_value={"purchase_id": 22})
        with patch("app.modules.purchases.service.PurchaseService", return_value=purchase_service):
            res = await execute_tool_action(
                "add_purchase",
                {"item_kind": "raw", "item_id": 2, "quantity": 4, "unit": "kg", "unit_price": 30},
            )
            assert res["success"] is True
            assert res["purchase_id"] == 22
            purchase_service.create_purchase_from_form.assert_awaited_once()
            fake_session.commit.assert_awaited()

    fake_session.commit.reset_mock()
    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        payment_service = MagicMock()
        payment_service.create_payment_from_form = AsyncMock(return_value=(33, "versement"))
        with patch("app.modules.payments.service.PaymentsService", return_value=payment_service):
            res = await execute_tool_action(
                "add_payment",
                {"client_id": 5, "amount": 1200, "payment_type": "versement"},
            )
            assert res["success"] is True
            assert res["payment_id"] == 33
            payment_service.create_payment_from_form.assert_awaited_once()
            fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_commercial_tools_reject_missing_item_before_service_call():
    sale_res = await execute_tool_action(
        "add_sale",
        {"item_kind": "finished", "quantity": 2, "unit": "kg", "unit_price": 50},
    )
    assert "error" in sale_res

    purchase_res = await execute_tool_action(
        "add_purchase",
        {"item_kind": "raw", "quantity": 2, "unit": "kg", "unit_price": 50},
    )
    assert "error" in purchase_res


@pytest.mark.asyncio
async def test_admin_user_tools_report_validation_errors():
    with patch("app.services.admin_service.create_user_account", new_callable=AsyncMock, return_value={"ok": False, "message": "Role invalide."}) as mock_create:
        res = await execute_tool_action("create_app_user", {"username": "ab", "password": "1", "role": "invalid"}, user_role="admin")
        assert "error" in res
        assert "Role invalide" in res["error"]
        mock_create.assert_awaited_once()

    with patch("app.services.auth_service.get_user_by_username", new_callable=AsyncMock) as mock_get_user:
        res = await execute_tool_action("change_app_user_password", {"username": "admin", "new_password": "12"}, user_role="admin")
        assert "error" in res
        mock_get_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_enum_values_tool():
    # Verify enum validation tool
    res = await execute_tool_action("get_enum_values", {"table": "expenses", "column": "payment_method"})
    assert "values" in res
    assert "cash" in res["values"]

def test_sanitize_numeric():
    assert sanitize_numeric("150,50") == 150.50
    assert sanitize_numeric(" 200 DA ") == 200.0
    assert sanitize_numeric("3 000,75 da") == 3000.75
    assert sanitize_numeric(12.34) == 12.34
    assert sanitize_numeric(None) == 0.0

@pytest.mark.asyncio
async def test_get_current_weather_tool():
    # Mock httpx response for wttr.in weather fetch
    from unittest.mock import MagicMock
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.text = "Paris: 🌦️ +14°C ↙️19km/h"
    with patch("httpx.AsyncClient.get", return_value=mock_res) as mock_get:
        res = await execute_tool_action("get_current_weather", {"location": "Paris"})
        assert "weather" in res
        assert "Paris: 🌦️" in res["weather"]
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_search_web_tool():
    from unittest.mock import MagicMock
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.text = """
    <div class="result results_links results_links_deep web-result ">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.google.com">Google Home Page</a>
      <div class="result__snippet">Google is the most popular search engine.</div>
    </div>
    """
    with patch("httpx.AsyncClient.get", return_value=mock_res) as mock_get:
        res = await execute_tool_action("search_web", {"query": "google"})
        assert "results" in res
        assert len(res["results"]) > 0
        assert res["results"][0]["title"] == "Google Home Page"
        assert res["results"][0]["url"] == "https://www.google.com"
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_get_business_insights_tool():
    # Mock database session execute return values
    from unittest.mock import MagicMock, AsyncMock
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchall.return_value = [("Client A", "0555000000", 15000.0)]
    mock_res.scalar.return_value = 50000.0
    mock_session.execute.return_value = mock_res

    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    with patch("app.core.async_db.get_async_sessionmaker", return_value=mock_session_maker):
        # We also mock async_cached_result to just call the builder
        async def mock_cached(key, builder, ttl_seconds=0):
            return await builder()
        with patch("app.core.perf_cache.async_cached_result", side_effect=mock_cached):
            res = await execute_tool_action("get_business_insights", {"insight_type": "top_debtors"})
            assert "top_debtors" in res
            assert res["top_debtors"][0]["name"] == "Client A"

            res_summary = await execute_tool_action("get_business_insights", {"insight_type": "summary"})
            assert "total_clients" in res_summary

@pytest.mark.asyncio
async def test_import_client_history_excel_tool():
    from unittest.mock import MagicMock, AsyncMock

    mock_service = MagicMock()
    mock_service.import_client_history_from_excel = AsyncMock(return_value={
        "client_id": 42,
        "client_name": "Test Client History",
        "nb_lignes": 15,
        "solde_final": 2500.0
    })

    mock_session_maker = MagicMock()

    with patch("app.core.async_db.get_async_sessionmaker", return_value=mock_session_maker):
        with patch("app.modules.clients.service.ClientService", return_value=mock_service):
            res = await execute_tool_action("import_client_history_excel", {"filepath": "test.xlsx", "client_id": 42})
            assert "success" in res
            assert res["success"] is True
            assert "15" in res["message"]
            assert "2500" in res["message"]

@pytest.mark.asyncio
async def test_execute_write_sql_auto_eval():
    from unittest.mock import MagicMock
    from app.modules.assistant.service import execute_write_sql

    mock_rows = [{"id": 12, "name": "Client Target", "current_balance": 15000.0}]

    with patch("app.core.db_helpers.db_manager.query_db", return_value=mock_rows) as mock_query:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_conn.execute.return_value = mock_cur

        mock_tx = MagicMock()
        mock_tx.__enter__.return_value = mock_conn

        with patch("app.core.db_helpers.db_manager.db_transaction", return_value=mock_tx):
            res = execute_write_sql("UPDATE clients SET notes = 'Updated' WHERE id = 12")
            assert "success" in res
            assert res["success"] is True
            assert "auto_evaluation" in res
            assert res["auto_evaluation"][0]["table_name"] == "clients"
            assert res["auto_evaluation"][0]["rows_affected_preview"] == 1
            assert res["auto_evaluation"][0]["preview_sample"][0]["name"] == "Client Target"
            mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_notes_tools():
    # Test execution of notes tools via execute_tool_action
    with patch("app.utils.tool_pages.list_user_notes", return_value=[{"id": "note_1", "title": "Test Note"}]) as mock_list:
        res = await execute_tool_action("list_user_notes", {})
        assert "notes" in res
        assert res["notes"][0]["id"] == "note_1"
        mock_list.assert_called_once()

    with patch("app.utils.tool_pages.get_user_note", return_value={"id": "note_1", "title": "Test Note", "content": "Hello"}) as mock_get:
        res = await execute_tool_action("get_user_note", {"note_id": "note_1"})
        assert "note" in res
        assert res["note"]["content"] == "Hello"
        mock_get.assert_called_once_with("note_1")

    with patch("app.utils.tool_pages.create_user_note", return_value={"id": "note_new", "title": "New Note"}) as mock_create:
        res = await execute_tool_action("create_user_note", {"title": "New Note", "content": "Body", "color": "blue"})
        assert "note" in res
        assert res["note"]["id"] == "note_new"
        mock_create.assert_called_once_with("New Note", "Body", "blue")

    with patch("app.utils.tool_pages.save_user_note", return_value={"id": "note_1", "title": "Updated"}) as mock_save:
        res = await execute_tool_action("save_user_note", {"note_id": "note_1", "title": "Updated", "content": "Body", "color": "yellow", "pinned": True})
        assert "note" in res
        assert res["note"]["title"] == "Updated"
        mock_save.assert_called_once_with("note_1", "Updated", "Body", "yellow", True)

    with patch("app.utils.tool_pages.delete_user_note", return_value=True) as mock_delete:
        res = await execute_tool_action("delete_user_note", {"note_id": "note_1"})
        assert "success" in res
        assert res["success"] is True
        mock_delete.assert_called_once_with("note_1")


# ===========================================================================
# Phase 2: SQL Guard allow-list tests
# ===========================================================================

def test_sql_guard_write_allow_list_blocks_unknown_table():
    """validate_write_sql should reject writes to tables not in ALLOWED_WRITE_TABLES."""
    from app.modules.assistant.sql_guard import validate_write_sql

    # Write to a known-allowed table → should pass (mocked DB connection is not called here)
    res_ok = validate_write_sql("INSERT INTO clients (name) VALUES ('Test')")
    assert res_ok.ok is True

    # Write to an unknown/unauthorized table → should be blocked
    res_bad = validate_write_sql("INSERT INTO some_unknown_table (col) VALUES ('x')")
    assert res_bad.ok is False
    assert "non autoris" in res_bad.error

    # Write to another unknown table via UPDATE
    res_update_bad = validate_write_sql("UPDATE shadow_table SET value = 'x' WHERE id = 1")
    assert res_update_bad.ok is False
    assert "non autoris" in res_update_bad.error

    # Write to suppliers (allowed) → should pass
    res_supplier = validate_write_sql(
        "INSERT INTO suppliers (name, phone) VALUES ('FournisseurTest', '0555000000')"
    )
    assert res_supplier.ok is True


def test_sql_guard_write_allow_list_passes_all_allowed_tables():
    """All tables in ALLOWED_WRITE_TABLES should be valid write targets."""
    from app.modules.assistant.sql_guard import validate_write_sql, ALLOWED_WRITE_TABLES

    # Test a subset of allowed tables to ensure they all pass
    test_queries = {
        "clients": "INSERT INTO clients (name) VALUES ('A')",
        "suppliers": "INSERT INTO suppliers (name) VALUES ('B')",
        "finished_products": "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost, alert_threshold) VALUES ('P', 'kg', 0, 100, 80, 5)",
        "raw_materials": "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty) VALUES ('M', 'kg', 0, 50, 60, 3, 5)",
        "sales": "UPDATE sales SET notes = 'x' WHERE id = 1",
        "expenses": "UPDATE expenses SET description = 'test' WHERE id = 1",
        "payments": "INSERT INTO payments (client_id, payment_type, amount, payment_date) VALUES (1, 'versement', 100, CURRENT_DATE)",
        "purchases": "INSERT INTO purchases (quantity, unit, unit_price, total, purchase_date) VALUES (10, 'kg', 100, 1000, CURRENT_DATE)",
        "production_batches": "INSERT INTO production_batches (finished_product_id, output_quantity, production_cost, unit_cost, production_date) VALUES (1, 10, 500, 50, CURRENT_DATE)",
        "saved_recipes": "INSERT INTO saved_recipes (finished_product_id, name) VALUES (1, 'Recette test')",
        "sabrina_memory": "INSERT INTO sabrina_memory (content, category, source) VALUES ('test', 'general', 'test')",
    }
    for table, query in test_queries.items():
        res = validate_write_sql(query)
        assert res.ok is True, f"Table '{table}' should be allowed but got error: {res.error}"


# ===========================================================================
# Phase 5: business_helpers tests
# ===========================================================================

def test_parse_french_date_basics():
    from datetime import date
    from app.modules.assistant.business_helpers import parse_french_date

    today = date(2024, 7, 15)

    assert parse_french_date("aujourd'hui", today) == today
    assert parse_french_date("hier", today) == date(2024, 7, 14)
    assert parse_french_date("avant-hier", today) == date(2024, 7, 13)
    assert parse_french_date("demain", today) == date(2024, 7, 16)
    assert parse_french_date("2024-07-05", today) == date(2024, 7, 5)
    assert parse_french_date("05/07/2024", today) == date(2024, 7, 5)


def test_parse_french_date_named_months():
    from datetime import date
    from app.modules.assistant.business_helpers import parse_french_date

    today = date(2024, 7, 15)

    assert parse_french_date("5 juillet", today) == date(2024, 7, 5)
    assert parse_french_date("le 5 juillet 2023", today) == date(2023, 7, 5)
    assert parse_french_date("15 janvier", today) == date(2024, 1, 15)
    assert parse_french_date("1 mars 2024", today) == date(2024, 3, 1)

    # Unrecognized → None
    assert parse_french_date("not a date") is None
    assert parse_french_date("") is None


def test_parse_amount_various_formats():
    from app.modules.assistant.business_helpers import parse_amount

    assert parse_amount(3500) == 3500.0
    assert parse_amount(3500.0) == 3500.0
    assert parse_amount("3 500 DA") == 3500.0
    assert parse_amount("3 500,50 DZD") == 3500.5
    assert parse_amount("45k") == 45000.0
    assert parse_amount("1,5 kg") == 1.5
    assert parse_amount("3.500,00") == 3500.0
    assert parse_amount("1 500 000") == 1500000.0
    assert parse_amount(None) == 0.0
    assert parse_amount("invalid") == 0.0


def test_get_enum_values_from_business_helpers():
    from app.modules.assistant.business_helpers import get_enum_values

    # Known table + column
    res = get_enum_values("expenses", "payment_method")
    assert "values" in res
    assert "cash" in res["values"]
    assert "cheque" in res["values"]

    res2 = get_enum_values("payments", "payment_type")
    assert "values" in res2
    assert "versement" in res2["values"]
    assert "avance" in res2["values"]

    # Unknown table
    res_unknown = get_enum_values("not_a_table", "col")
    assert "error" in res_unknown

    # Unknown column on known table
    res_bad_col = get_enum_values("expenses", "non_existent_column")
    assert "error" in res_bad_col


def test_sql_guard_write_blocks_users_table():
    """Users table should be caught by protected table check before allow-list."""
    from app.modules.assistant.sql_guard import validate_write_sql

    res = validate_write_sql("UPDATE users SET role = 'admin' WHERE id = 1")
    assert res.ok is False
    assert "proteg" in res.error


def test_model_selection_not_overridden():
    """
    Verify that the auto-selection logic in run_assistant_agent_generator
    only fires when user_model is 'auto' or empty, not when a specific model is chosen.
    """
    import inspect
    from app.modules.assistant import service

    source = inspect.getsource(service.run_assistant_agent_generator)

    # The fix: auto-selection should only happen for 'auto' or empty model
    assert "user_model.lower() in (\"auto\", \"\")" in source, (
        "Model auto-selection should only fire for auto/empty values, "
        "not override a user-selected model"
    )
    # The old forced override pattern should not be present
    assert "user_model = \"gemini-3.5-flash\"" not in source or "complexity" in source, (
        "Model should only be set to gemini-3.5-flash inside the auto-selection block"
    )
    assert "user_model = \"gemini-3.1-flash-lite\"" not in source or "complexity" in source, (
        "Model should only be set to gemini-3.1-flash-lite inside the auto-selection block"
    )


def test_schema_context_exports():
    """Verify that schemas and prompt formatting functions are exported correctly from schema_context."""
    from app.modules.assistant.schema_context import TABLE_SCHEMAS, get_schema, get_sabrina_system_prompt
    
    assert "clients" in TABLE_SCHEMAS
    assert "sales" in TABLE_SCHEMAS
    
    schema = get_schema()
    assert "schema" in schema
    assert "clients" in schema["schema"]
    
    prompt = get_sabrina_system_prompt("gemini-3.1-flash-lite")
    assert "Sabrina" in prompt
    assert "DZD" in prompt


def test_classify_intent():
    """Verify that classify_intent correctly identifies lite and full (complex) user queries."""
    from app.modules.assistant.intent import classify_intent
    
    # Lite queries
    assert classify_intent("bonjour") == "lite"
    assert classify_intent("salut") == "lite"
    assert classify_intent("") == "lite"
    assert classify_intent("merci beaucoup") == "lite"
    
    # Complex (full) queries
    assert classify_intent("crée un nouveau client nommé Massi") == "full"
    assert classify_intent("supprimer la vente avec ID 5412") == "full"
    assert classify_intent("affiche le rapport des bénéfices du mois dernier") == "full"
    assert classify_intent("montre l'état du stock de matière première") == "full"
    assert classify_intent("générer un bon de livraison PDF") == "full"


@pytest.mark.asyncio
async def test_delete_operation_tool_action():
    from unittest.mock import MagicMock
    
    mock_sales_service = MagicMock()
    mock_sales_service.delete_sale_by_id = AsyncMock(return_value=True)
    
    mock_purchase_service = MagicMock()
    mock_purchase_service.delete_purchase_by_id = AsyncMock(return_value=True)

    mock_payments_service = MagicMock()
    mock_payments_service.delete_payment_by_id = AsyncMock(return_value=True)

    with patch("app.modules.sales.service.SalesService", return_value=mock_sales_service):
        with patch("app.modules.purchases.service.PurchaseService", return_value=mock_purchase_service):
            with patch("app.modules.payments.service.PaymentsService", return_value=mock_payments_service):
                # 1. Test sale_finished mapping
                res_finished = await execute_tool_action("delete_operation", {"tx_kind": "sale_finished", "tx_id": 123})
                assert res_finished["success"] is True
                mock_sales_service.delete_sale_by_id.assert_called_with("finished", 123)

                # 2. Test sale_raw mapping
                res_raw = await execute_tool_action("delete_operation", {"tx_kind": "sale_raw", "tx_id": 456})
                assert res_raw["success"] is True
                mock_sales_service.delete_sale_by_id.assert_called_with("raw", 456)

                # 3. Test generic sale fallback mapping when it doesn't exist in finished (so it queries)
                mock_sales_service.sale_repo.get_sale_detail = AsyncMock(return_value=None)
                res_generic_raw = await execute_tool_action("delete_operation", {"tx_kind": "sale", "tx_id": 789})
                assert res_generic_raw["success"] is True
                mock_sales_service.delete_sale_by_id.assert_called_with("raw", 789)

                # 4. Test purchase mapping
                res_purchase = await execute_tool_action("delete_operation", {"tx_kind": "purchase", "tx_id": 111})
                assert res_purchase["success"] is True
                mock_purchase_service.delete_purchase_by_id.assert_called_with(111)

                # 5. Test payment mapping
                res_payment = await execute_tool_action("delete_operation", {"tx_kind": "payment", "tx_id": 222})
                assert res_payment["success"] is True
                mock_payments_service.delete_payment_by_id.assert_called_with(222)


@pytest.mark.asyncio
async def test_admin_tools_role_security():
    from app.modules.assistant.tool_actions import execute_tool_action
    from unittest.mock import MagicMock, AsyncMock, patch
    
    # 1. An operator attempting to call create_app_user should be blocked
    res_blocked = await execute_tool_action(
        "create_app_user",
        {"username": "hacker", "password": "123", "role": "admin"},
        user_role="operator"
    )
    assert "error" in res_blocked
    assert "réservée aux administrateurs" in res_blocked["error"].lower()

    # 2. An admin attempting to call create_app_user should be allowed (mock service)
    fake_session = AsyncMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    fake_session_maker = MagicMock(return_value=fake_cm)

    with patch("app.core.async_db.get_async_sessionmaker", return_value=fake_session_maker):
        with patch("app.services.admin_service.create_user_account", new_callable=AsyncMock, return_value={"ok": True, "message": "created"}) as mock_create:
            res_allowed = await execute_tool_action(
                "create_app_user",
                {"username": "new_user", "password": "password", "role": "operator"},
                user_role="admin"
            )
            assert "success" in res_allowed
            assert res_allowed["success"] is True
            mock_create.assert_awaited_once_with("new_user", "password", "operator")



