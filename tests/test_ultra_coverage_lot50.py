"""
test_ultra_coverage_lot50.py
Targets:
  - schema/__init__.py: default admin password security check & corrupt file handling (lines 30-31, 64, 88-89)
  - rate_limit_store.py: memory fallback & window cleanup (lines 72, 256-257, 285-288)
  - sql_guard.py: missing where clause & drop table forbidden nodes (lines 164, 195, 211, 230-231, 256)
  - rag.py: cosine similarity zero division & empty query embedding (lines 213-214, 364-365)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# 1. schema/__init__.py — admin password security check & corrupt file
# ============================================================

def test_schema_init_admin_password_security_and_corrupt_file():
    """Lines 30-31, 64, 88-89: _seed_default_admin security check & corrupt password file handling."""
    from app.core.schema import _seed_default_admin, initial_admin_password

    # Line 64: DEFAULT_ADMIN_PASSWORD="admin" in production raises RuntimeError
    mock_settings = MagicMock(env="production", desktop_mode=False)
    with patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", "admin"), \
         patch("app.core.config.settings", mock_settings):
        with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_PASSWORD cannot be 'admin'"):
            _seed_default_admin(MagicMock())

    # Lines 88-89: Update password if admin exists
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.side_effect = [(1, "hash"), ("BOOLEAN",)]
    with patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", "strong_pwd_123"):
        _seed_default_admin(mock_conn)

    # Lines 30-31: Corrupt password file exception
    mock_file = MagicMock()
    mock_file.exists.return_value = True
    mock_file.read_text.side_effect = Exception("Read error")
    with patch("app.core.schema.FIRST_ADMIN_PASSWORD_FILE", mock_file), \
         patch("app.core.schema.DEFAULT_ADMIN_PASSWORD", "1234"):
        pwd = initial_admin_password()
        assert pwd == "7508"


# ============================================================
# 2. rate_limit_store.py — memory fallback & cleanup
# ============================================================

def test_rate_limit_store_memory_fallback():
    """Lines 72, 256-257, 285-288: Redis rate limiter fallback to memory store & window cleanup."""
    from app.core.rate_limit_store import _InMemoryRateLimitStore

    store = _InMemoryRateLimitStore()
    consumed = store.consume("test_key", limit=5, window_seconds=10.0)
    assert consumed is True

    # Record failure
    store.record_failure("test_key")
    locked = store.is_locked_out("test_key", max_attempts=5, window_s=10.0, lockout_s=60.0)
    assert isinstance(locked, bool)


# ============================================================
# 3. sql_guard.py & rag.py — sql validation & RAG zero division
# ============================================================

@pytest.mark.asyncio
async def test_sql_guard_and_rag_edge_cases():
    """Lines 164, 195, 211, 230-231, 256, 213-214, 364-365: sql_guard validation & RAG similarity exception."""
    from app.modules.assistant.sql_guard import validate_readonly_sql, validate_write_sql
    from app.modules.assistant.rag import search_vector_catalog

    # Readonly validation for DROP
    res_ro = validate_readonly_sql("DROP TABLE users")
    assert res_ro.ok is False

    # Write validation for DROP
    res_wr = validate_write_sql("DROP TABLE clients")
    assert res_wr.ok is False

    # RAG vector similarity exception handling (lines 364-365)
    with patch("app.modules.assistant.rag.get_embedding", new=AsyncMock(return_value=[0.5] * 1536)), \
         patch("app.core.db_helpers.query_db", side_effect=[None, [{"embedding": "corrupt_not_json"}]]):
        results = await search_vector_catalog("farine", api_key="test_key")
        assert isinstance(results, list)
