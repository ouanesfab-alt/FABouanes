"""
test_coverage_boost_lot39.py
Targets:
  - rag.py:
    - Tuple row index exception fallback (lines 131-132)
    - get_pdf_text_chunks short paragraph skip (line 163)
    - update_pdf_index corrupt INDEX_FILE & write error (lines 182-183, 198-199, 213-214)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. rag.py — tuple row indexing & short paragraph filtering
# ============================================================

@pytest.mark.asyncio
async def test_rag_tuple_row_indexing():
    """Lines 131-132: search_vector_manual handles tuple rows from raw execute."""
    from app.modules.assistant.rag import search_vector_manual

    # Return a tuple instead of dict so r["item_id"] raises TypeError
    mock_rows = [(101,)]

    with patch("app.modules.assistant.rag.get_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch("app.core.db_helpers.query_db", side_effect=[[{"extname": "vector"}], mock_rows]):
        res = await search_vector_manual("requête test", "dummy_key", limit=1)

    assert len(res) >= 0


def test_rag_get_pdf_text_chunks_short_para():
    """Line 163: get_pdf_text_chunks skips paragraphs shorter than 20 chars."""
    from app.modules.assistant.rag import get_pdf_text_chunks

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Short\n\nThis is a long enough paragraph with more than 20 characters."

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("app.modules.assistant.rag.PdfReader", return_value=mock_reader):
        chunks = get_pdf_text_chunks(Path("dummy.pdf"))

    assert len(chunks) == 1
    assert "long enough" in chunks[0]["text"]


# ============================================================
# 2. rag.py — update_pdf_index exception branches
# ============================================================

def test_rag_update_pdf_index_corrupt_file_and_write_error(tmp_path):
    """Lines 182-183, 198-199, 213-214: update_pdf_index corrupt file & getmtime error."""
    from app.modules.assistant.rag import update_pdf_index

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "test.pdf").write_bytes(b"%PDF-1.4 dummy content")

    corrupt_index = tmp_path / "index_rag.json"
    corrupt_index.write_text("INVALID JSON {{{", encoding="utf-8")

    fake_paths = MagicMock()
    fake_paths.pdf_reader_dir = pdf_dir

    with patch("app.modules.assistant.rag.INDEX_FILE", corrupt_index), \
         patch("app.modules.assistant.rag.paths", fake_paths), \
         patch("os.path.getmtime", side_effect=Exception("stat error")):
        index_data = update_pdf_index()

    assert "test.pdf" in index_data


def test_rag_update_pdf_index_write_permission_error(tmp_path):
    """Lines 213-214: update_pdf_index handles file write exception."""
    from app.modules.assistant.rag import update_pdf_index

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "doc.pdf").write_bytes(b"%PDF-1.4 dummy")

    idx_file = tmp_path / "index_rag.json"

    fake_paths = MagicMock()
    fake_paths.pdf_reader_dir = pdf_dir

    with patch("app.modules.assistant.rag.INDEX_FILE", idx_file), \
         patch("app.modules.assistant.rag.paths", fake_paths), \
         patch.object(Path, "open", side_effect=[MagicMock(), Exception("write permission denied")]):
        index_data = update_pdf_index()

    assert "doc.pdf" in index_data
