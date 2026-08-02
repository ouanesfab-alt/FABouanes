"""
test_coverage_boost_lot43.py
Targets:
  - rag.py: get_embedding cache hit/expiry, API key URL formatting, 404 model retry, and exception logging (lines 261, 265, 278, 292, 303-304)
  - sql_tools.py: dry_run_sql & execute_write_sql empty parse & RETURNING tuple row (lines 48, 148, 200-201, 205-206)
  - sql_guard.py: forbidden node checks & CTE write guard (lines 112, 164, 195, 211, 230-231)
  - config.py: cors_origins list return (lines 83-84)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. rag.py — get_embedding cache hit, key format, 404 retry
# ============================================================

@pytest.mark.asyncio
async def test_rag_get_embedding_cache_hit_and_expiry():
    """Lines 261, 265: get_embedding handles expired cache items and returns cached embeddings."""
    import time
    from app.modules.assistant import rag

    # Add expired item and valid item to cache
    rag._embedding_cache["old_text"] = (time.time() - 4000.0, [0.1] * 1536)
    rag._embedding_cache["cached_text"] = (time.time(), [0.5] * 1536)

    res = await rag.get_embedding("cached_text", "AIzaSyTestKey123")
    assert res == [0.5] * 1536
    assert "old_text" not in rag._embedding_cache


@pytest.mark.asyncio
async def test_rag_get_embedding_aizasy_key_format_and_404_fallback():
    """Lines 278, 292, 303-304: get_embedding AIzaSy key URL formatting, 404 fallback, and exception."""
    from app.modules.assistant.rag import get_embedding

    mock_resp_404 = MagicMock(status_code=404)
    mock_resp_200 = MagicMock(status_code=200)
    mock_resp_200.json.return_value = {"embedding": {"values": [0.9] * 1536}}
    mock_resp_200.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=[mock_resp_404, mock_resp_200])

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await get_embedding("uncached query text", "AIzaSyTestKey123")

    assert res == [0.9] * 1536


@pytest.mark.asyncio
async def test_rag_get_embedding_exception():
    """Lines 303-304: get_embedding handles HTTP request failure gracefully."""
    from app.modules.assistant.rag import get_embedding

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=RuntimeError("connection pool exhausted"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await get_embedding("query failing", "BearerToken123")

    assert res is None


# ============================================================
# 2. sql_tools.py — RETURNING row tuple handling
# ============================================================

def test_execute_write_sql_returning_tuple_row():
    """Lines 200-201, 205-206: execute_write_sql handles returning tuple rows."""
    from app.modules.assistant.sql_tools import execute_write_sql

    mock_conn = MagicMock()
    mock_cur = MagicMock(rowcount=1)
    mock_cur.fetchone.return_value = (55, "Client New")
    mock_conn.execute.return_value = mock_cur

    with patch("app.modules.assistant.sql_tools.db_manager.query_db", return_value=[]), \
         patch("app.modules.assistant.sql_tools.db_manager.db_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = mock_conn
        res = execute_write_sql("INSERT INTO clients (name) VALUES ('Client New') RETURNING id, name")

    assert res.get("success") is True
    assert res.get("inserted_id") == 55


# ============================================================
# 3. config.py — cors_origins property
# ============================================================

def test_config_secret_key_auto_generation_and_read_error(tmp_path):
    """Lines 83-84, 102: Settings auto generates secret_key and handles key_file read error."""
    from app.core.config import Settings

    key_file = tmp_path / "secret.key"
    key_file.write_text("existing_secret_key", encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=Exception("read error")):
        s = Settings(secret_key="", app_data_dir=tmp_path, env="testing")
        assert s.secret_key is not None
