import pytest
from unittest.mock import patch, AsyncMock
from app.modules.assistant.service import (
    execute_readonly_sql,
    run_assistant_agent,
    dry_run_sql,
    execute_tool_action,
    compress_history_if_needed,
    get_ollama_tools,
    sanitize_numeric
)
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
        assert len(compressed) <= 7
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
            assert res["auto_evaluation"]["table_name"] == "clients"
            assert res["auto_evaluation"]["rows_affected_preview"] == 1
            assert res["auto_evaluation"]["preview_sample"][0]["name"] == "Client Target"
            mock_query.assert_called_once()

