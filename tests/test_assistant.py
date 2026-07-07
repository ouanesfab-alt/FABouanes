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
    res = dry_run_sql("UPDATE clients SET debt = 100 WHERE id = 99999")
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

