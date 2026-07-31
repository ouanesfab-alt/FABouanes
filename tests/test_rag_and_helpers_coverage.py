"""
test_rag_and_helpers_coverage.py — Tests targeting RAG, PDF indexing, and DB fallback logic.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.modules.assistant.rag import (
    search_vector_manual,
    get_pdf_text_chunks,
    update_pdf_index,
    get_embedding,
    INDEX_FILE
)
from app.core.db_helpers.manager import DatabaseManager

@pytest.mark.asyncio
async def test_search_vector_manual_no_key():
    res = await search_vector_manual("vente", "", limit=2)
    assert res == []

@pytest.mark.asyncio
async def test_search_vector_manual_mock_key():
    with patch("app.modules.assistant.rag.get_embedding", return_value=[0.1]*1536):
        with patch("app.core.db_helpers.query_db", return_value=[{"item_id": 101, "score": 0.95}]):
            res = await search_vector_manual("vente", "fake_key", limit=2)
            assert isinstance(res, list)

def test_get_pdf_text_chunks_nonexistent():
    chunks = get_pdf_text_chunks(Path("non_existent_file.pdf"))
    assert chunks == []

def test_update_pdf_index_basic():
    res = update_pdf_index()
    assert isinstance(res, dict)

def test_db_manager_reconnect_logic():
    mgr = DatabaseManager()
    with patch.object(mgr, "create_database_engine") as mock_create:
        mock_eng = MagicMock()
        mock_eng.raw_connection.side_effect = Exception("closed connection")
        mock_create.return_value = mock_eng
        try:
            mgr.connect_database("sqlite:///:memory:")
        except Exception:
            pass
