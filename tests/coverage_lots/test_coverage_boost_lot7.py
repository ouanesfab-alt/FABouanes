"""Tests de couverture ciblés — Lot 7.

Couvre: assistant/rag.py (normalize_text, search_manual, get_pdf_text_chunks, update_pdf_index, search_user_documents),
        security.py (encrypt_val, decrypt_val, get_client_key_sync, create_client_key_sync, delete_client_key_sync)
"""
from __future__ import annotations

import os
from unittest.mock import patch


# ── assistant/rag.py (69% → target ~90%) ────────────────────────────


def test_rag_normalize_text():
    """normalize_text strips accents, lowers text, removes special chars."""
    from app.modules.assistant.rag import normalize_text
    assert normalize_text("Facture N° 123 - Vente Électronique") == "facture n 123 vente electronique"


def test_rag_search_manual_empty():
    """search_manual with empty query returns empty list."""
    from app.modules.assistant.rag import search_manual
    assert search_manual("") == []
    assert search_manual("a") == []  # < 3 chars


def test_rag_search_manual_valid_keyword():
    """search_manual returns matching chapters for valid keyword."""
    from app.modules.assistant.rag import search_manual
    results = search_manual("facture vente", limit=2)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "chapter_id" in results[0]
    assert "fr_title" in results[0]


def test_rag_get_pdf_text_chunks_nonexistent():
    """get_pdf_text_chunks handles non-existent file gracefully."""
    from pathlib import Path
    from app.modules.assistant.rag import get_pdf_text_chunks

    chunks = get_pdf_text_chunks(Path("non_existent_file.pdf"))
    assert chunks == []


def test_rag_search_user_documents_empty_query():
    """search_user_documents returns empty list for short query."""
    from app.modules.assistant.rag import search_user_documents
    assert search_user_documents("") == []


def test_rag_update_pdf_index():
    """update_pdf_index reads pdf_reader_dir and returns index dict."""
    from app.modules.assistant.rag import update_pdf_index
    res = update_pdf_index()
    assert isinstance(res, dict)


# ── security.py encryption & client keys (87% → target ~95%) ───────


def test_encrypt_val_none():
    """encrypt_val returns None for None input."""
    from app.core.security import encrypt_val
    assert encrypt_val(None, b"0" * 32) is None


def test_encrypt_val_empty():
    """encrypt_val encrypts empty string with prefix ale:."""
    from app.core.security import encrypt_val
    res = encrypt_val("", b"0" * 32)
    assert res is not None
    assert res.startswith("ale:")


def test_encrypt_val_import_error():
    """encrypt_val returns unencrypted val on ImportError."""
    import sys
    with patch.dict(sys.modules, {"cryptography.hazmat.primitives.ciphers.aead": None}):
        from app.core.security import encrypt_val
        assert encrypt_val("secret", b"0" * 32) == "secret"



def test_encrypt_and_decrypt_val_roundtrip():
    """encrypt_val and decrypt_val roundtrip successfully with AESGCM."""
    from app.core.security import encrypt_val, decrypt_val
    key = os.urandom(32)

    original = "Information confidentielle client 123"
    encrypted = encrypt_val(original, key)

    assert encrypted is not None
    assert encrypted.startswith("ale:")

    decrypted = decrypt_val(encrypted, key)
    assert decrypted == original


def test_decrypt_val_none_or_empty():
    """decrypt_val handles None and empty string."""
    from app.core.security import decrypt_val
    assert decrypt_val(None, b"0" * 32) is None
    assert decrypt_val("", b"0" * 32) == ""
    assert decrypt_val("plain_string", b"0" * 32) == "plain_string"


def test_decrypt_val_missing_key():
    """decrypt_val returns deleted placeholder if key is None for encrypted string."""
    from app.core.security import decrypt_val
    assert decrypt_val("ale:dGVzdGRhdGE=", None) == "[DONNÉES SUPPRIMÉES]"


def test_decrypt_val_invalid_payload():
    """decrypt_val returns deleted placeholder on corrupt payload."""
    from app.core.security import decrypt_val
    key = os.urandom(32)
    assert decrypt_val("ale:short", key) == "[DONNÉES SUPPRIMÉES]"
    assert decrypt_val("ale:invalid_base64_payload!!!", key) == "[DONNÉES SUPPRIMÉES]"


def test_get_client_key_sync():
    """get_client_key_sync fetches and base64-decodes key from DB."""
    from app.core.security import get_client_key_sync
    import base64

    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("utf-8")

    with patch("app.core.db_helpers.query_db") as mock_query:
        mock_query.return_value = {"encryption_key": b64_key}
        key = get_client_key_sync(10)
        assert key == raw_key

        mock_query.return_value = None
        assert get_client_key_sync(99) is None


def test_create_client_key_sync():
    """create_client_key_sync generates 32-byte key and saves to DB."""
    from app.core.security import create_client_key_sync

    with patch("app.core.db_helpers.execute_db") as mock_exec:
        key = create_client_key_sync(15)
        assert isinstance(key, bytes)
        assert len(key) == 32
        assert mock_exec.called


def test_delete_client_key_sync():
    """delete_client_key_sync deletes client key from DB."""
    from app.core.security import delete_client_key_sync

    with patch("app.core.db_helpers.execute_db") as mock_exec:
        delete_client_key_sync(15)
        assert mock_exec.called
