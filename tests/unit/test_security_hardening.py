import pytest
import os
import json
import asyncio
from unittest.mock import MagicMock, patch
from fastapi import Request
from starlette.datastructures import Headers

from app.core.db_helpers import split_sql_script, validate_identifier
from app.core.security import get_client_fingerprint
from app.core.rate_limit_store import _RedisRateLimitStore
from app.core.events import DomainEvent, emit
from app.core.worker import dispatch_outbox_events_task
from app.core.db_access import execute_db, query_db

def test_split_sql_script_with_comments():
    script_with_comments = """
    -- This is a comment at the beginning;
    CREATE TABLE test_comments (
        id INT PRIMARY KEY,
        name TEXT -- inline comment with semicolon;
    );
    /* Multi-line comment
       containing ; semicolons and quotes 'hello'
    */
    INSERT INTO test_comments (id, name) VALUES (1, 'val');
    """
    statements = split_sql_script(script_with_comments)
    assert len(statements) == 2
    assert "CREATE TABLE test_comments" in statements[0]
    assert "INSERT INTO test_comments" in statements[1]
    assert "--" not in statements[0]
    assert "/*" not in statements[1]

def test_validate_identifier():
    # Sûrs
    validate_identifier("sales")
    validate_identifier("raw_materials")
    validate_identifier("s.id")
    
    # Non sûrs
    with pytest.raises(ValueError):
        validate_identifier("sales; DROP TABLE users;")
    with pytest.raises(ValueError):
        validate_identifier("sales--")
    with pytest.raises(ValueError):
        validate_identifier("")

def test_fingerprint_generation():
    class DummyRequest:
        def __init__(self, headers, client_host="127.0.0.1"):
            self.headers = Headers(headers)
            self.client = type("Client", (), {"host": client_host})()
            self.url = type("URL", (), {"scheme": "http", "path": "/"})()
            self.method = "GET"
            self.scope = {"type": "http"}

    req1 = DummyRequest({"User-Agent": "Mozilla/5.0"}, "192.168.1.1")
    req2 = DummyRequest({"User-Agent": "Mozilla/5.0"}, "192.168.1.1")
    req3 = DummyRequest({"User-Agent": "Chrome/1.0"}, "192.168.1.1")
    req4 = DummyRequest({"User-Agent": "Mozilla/5.0"}, "192.168.1.2")

    with patch("app.core.security.get_state_value", return_value=req1):
        fp1 = get_client_fingerprint(req1)
        
    with patch("app.core.security.get_state_value", return_value=req2):
        fp2 = get_client_fingerprint(req2)
        
    with patch("app.core.security.get_state_value", return_value=req3):
        fp3 = get_client_fingerprint(req3)
        
    with patch("app.core.security.get_state_value", return_value=req4):
        fp4 = get_client_fingerprint(req4)

    assert fp1 == fp2
    assert fp1 != fp3
    assert fp1 != fp4

def test_redis_rate_limit_store():
    # Mock Redis client
    mock_client = MagicMock()
    mock_pipe = MagicMock()
    mock_client.pipeline.return_value = mock_pipe
    
    # Simulate zcard count of 2 (under limit of 3)
    mock_pipe.execute.return_value = [1, 2, True, True]
    
    store = _RedisRateLimitStore(mock_client)
    assert store.consume("test_redis_key", limit=3, window_seconds=10.0) is True
    
    # Simulate zcard count of 3 (at limit)
    mock_pipe.execute.return_value = [1, 3, True, True]
    assert store.consume("test_redis_key", limit=3, window_seconds=10.0) is False
    mock_client.zrem.assert_called()

def test_outbox_emission_and_dispatch(monkeypatch):
    # Force outbox usage
    monkeypatch.setenv("FAB_FORCE_OUTBOX", "1")
    
    # Clean the outbox table
    execute_db("DELETE FROM outbox_events")
    
    # Emit a test event
    event = DomainEvent(action="create", entity_type="test_outbox_entity", entity_id=99, label="Outbox Test")
    emit(event)
    
    # Check it was written to outbox table
    rows = query_db("SELECT id, event_type, payload FROM outbox_events WHERE processed_at IS NULL")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "create.test_outbox_entity"
    
    # Dispatch event
    with patch("app.core.events._redis_client") as mock_redis:
        processed = asyncio.run(dispatch_outbox_events_task({}))
        assert processed == 1
        
    # Verify it is marked processed
    rows_after = query_db("SELECT id, processed_at FROM outbox_events WHERE id = %s", (rows[0]["id"],))
    assert rows_after[0]["processed_at"] is not None
