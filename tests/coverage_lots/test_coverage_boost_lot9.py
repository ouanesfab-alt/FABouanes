"""Tests de couverture ciblés — Lot 9.

Couvre: assistant/rag.py (search_vector_catalog cosine fallback, get_rag_context markdown formatting)
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch


# ── assistant/rag.py (70% → target ~90%) ────────────────────────────


@pytest.mark.asyncio
async def test_search_vector_catalog_no_api_key():
    """search_vector_catalog returns empty list when api_key is empty."""
    from app.modules.assistant.rag import search_vector_catalog
    res = await search_vector_catalog("farine", "")
    assert res == []


@pytest.mark.asyncio
async def test_search_vector_catalog_python_cosine_fallback():
    """search_vector_catalog uses in-memory cosine similarity when pgvector is unavailable."""
    from app.modules.assistant.rag import search_vector_catalog

    dummy_emb = [0.1] * 1536
    item_emb_str = json.dumps(dummy_emb)

    mock_db_rows = [
        {
            "item_kind": "raw_material",
            "item_id": 1,
            "text_content": "Farine de blé 50kg",
            "embedding": item_emb_str,
        }
    ]

    with patch("app.modules.assistant.rag.get_embedding", new_callable=AsyncMock) as mock_emb, \
         patch("app.core.db_helpers.query_db") as mock_query:

        mock_emb.return_value = dummy_emb

        def mock_query_side_effect(sql, params=(), one=False):
            if "vector" in sql and "pg_extension" in sql:
                return None  # no pgvector
            if "catalog_embeddings" in sql:
                return mock_db_rows
            return None

        mock_query.side_effect = mock_query_side_effect

        results = await search_vector_catalog("farine", "AIzaSyTestApiKey", limit=3)
        assert len(results) == 1
        assert results[0]["kind"] == "raw_material"
        assert results[0]["id"] == 1
        assert results[0]["score"] >= 0.5


def test_get_rag_context_empty_query():
    """get_rag_context returns empty string for empty query."""
    from app.modules.assistant.rag import get_rag_context
    assert get_rag_context("") == ""


def test_get_rag_context_manual_matches():
    """get_rag_context formats manual chapters into markdown block."""
    from app.modules.assistant.rag import get_rag_context

    with patch("app.modules.assistant.rag.search_user_documents", return_value=[]), \
         patch("app.modules.assistant.rag.search_manual") as mock_manual, \
         patch("app.modules.assistant.schema_context.get_gemini_api_key", return_value=None):

        mock_manual.return_value = [
            {
                "chapter_id": "1-1",
                "fr_title": "Gestion des Ventes",
                "ar_title": "إدارة المبيعات",
                "fr_usage": ["Étape 1: Créer la vente"],
                "ar_usage": ["الخطوة 1: إنشاء المبيعات"],
                "fr_example": "Vente de pain 10kg",
                "ar_example": "بيع الخبز 10 كجم",
            }
        ]

        context = get_rag_context("vente client")
        assert "MANUEL UTILISATEUR" in context
        assert "Gestion des Ventes" in context
        assert "إدارة المبيعات" in context
        assert "Étape 1" in context


def test_get_rag_context_no_matches_returns_empty():
    """get_rag_context returns empty string if no matches found."""
    from app.modules.assistant.rag import get_rag_context

    with patch("app.modules.assistant.rag.search_user_documents", return_value=[]), \
         patch("app.modules.assistant.rag.search_manual", return_value=[]), \
         patch("app.modules.assistant.schema_context.get_gemini_api_key", return_value=None):

        assert get_rag_context("mot_cle_inexistant_xyz_123") == ""
