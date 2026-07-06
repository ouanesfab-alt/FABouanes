import pytest
from unittest.mock import patch, AsyncMock
from app.modules.assistant.service import execute_readonly_sql, run_assistant_agent
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
