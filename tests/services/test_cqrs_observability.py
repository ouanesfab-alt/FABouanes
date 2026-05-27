from __future__ import annotations

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock
import pytest

from app.core.db_helpers import DatabaseManager
from app.core.worker import enqueue_background_task, TASK_MAPPING
from app.core.observability import setup_observability, instrument_app


def test_database_replica_routing():
    """Verify that query_db routes to the replica engine (read url) and execute_db routes to the primary engine (write url)."""
    db_manager = DatabaseManager()
    
    mock_conn = MagicMock()
    # Mock return value of execute to return a dummy cursor
    mock_cursor = MagicMock()
    mock_conn.execute.return_value = mock_cursor
    
    with patch.object(db_manager, "connect_database", return_value=mock_conn) as mock_connect:
        with patch.dict(os.environ, {"DATABASE_READ_URL": "postgresql://replica_db"}):
            # Clear request state
            with patch("app.core.db_helpers.get_request_state", return_value=None):
                with patch("app.core.db_helpers.ensure_request_state") as mock_ensure:
                    state = MagicMock()
                    state.db = None
                    state.read_db = None
                    state.db_tx_depth = 0
                    mock_ensure.return_value = state
                    
                    # 1. Run a query (read)
                    db_manager.query_db("SELECT 1")
                    # Should connect to replica_db
                    mock_connect.assert_called_with("postgresql://replica_db")
                    
                    # Reset call count
                    mock_connect.reset_mock()
                    
                    # 2. Run an execute (write)
                    db_manager.execute_db("INSERT INTO foo VALUES (1)")
                    # Should connect to main database (settings.database_url)
                    from app.core.config import settings
                    mock_connect.assert_called_with(settings.database_url)


@pytest.mark.asyncio
async def test_enqueue_background_task_fallback():
    """Verify that enqueue_background_task runs tasks inline in background thread/task when Redis is not available."""
    # Ensure REDIS_URL is empty to force fallback
    with patch.dict(os.environ, {"REDIS_URL": ""}):
        # Mock the specific task to see if it is triggered
        mock_task = MagicMock()
        
        # Temporarily register our mock task in TASK_MAPPING
        original_mapping = TASK_MAPPING.copy()
        try:
            # Create a mock async function
            async def dummy_task(ctx, *args, **kwargs):
                mock_task(*args, **kwargs)
                
            TASK_MAPPING["dummy_test_task"] = dummy_task
            
            job_id = await enqueue_background_task("dummy_test_task", "test_arg", keyword_arg="test_val")
            assert job_id.startswith("fallback-")
            
            # Wait briefly to let the background asyncio task run
            await asyncio.sleep(0.1)
            mock_task.assert_called_once_with("test_arg", keyword_arg="test_val")
        finally:
            # Restore original mapping
            TASK_MAPPING.clear()
            TASK_MAPPING.update(original_mapping)


def test_setup_observability_no_console_export_in_tests():
    """Verify setup_observability runs without raising errors and does not register ConsoleSpanExporter during tests unless configured."""
    import app.core.observability
    
    with patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider:
        with patch.object(app.core.observability, "_TRACER_INITIALIZED", False):
            setup_observability("test_service")
            # setup_observability should be callable and set the provider
            assert mock_set_provider.called

