"""Tests for app.core.perf_cache — InMemoryCache backend.

These tests exercise the InMemoryCache class *directly* (not the global
singleton) so they are fully isolated and need no database.
"""
from __future__ import annotations

import time

import pytest

from app.core.perf_cache import InMemoryCache


class TestInMemoryCache:
    """Unit tests for InMemoryCache."""

    def setup_method(self) -> None:
        self.cache = InMemoryCache()

    # ------------------------------------------------------------------
    # Basic set / get
    # ------------------------------------------------------------------

    def test_set_and_get(self) -> None:
        """Storing a value and retrieving it should work when the
        fingerprint matches the current cache generation (v:0)."""
        self.cache.set(("test", "key1"), {"data": 42}, ttl=60.0, fingerprint="v:0")
        result = self.cache.get(("test", "key1"))
        assert result == {"data": 42}

    def test_get_missing_key_returns_none(self) -> None:
        assert self.cache.get(("no", "such", "key")) is None

    def test_overwrite_existing_key(self) -> None:
        self.cache.set(("k",), "first", ttl=60.0, fingerprint="v:0")
        self.cache.set(("k",), "second", ttl=60.0, fingerprint="v:0")
        assert self.cache.get(("k",)) == "second"

    # ------------------------------------------------------------------
    # TTL / expiry
    # ------------------------------------------------------------------

    def test_get_expired_returns_none(self) -> None:
        """An entry whose TTL has elapsed should not be returned."""
        # TTL is clamped to min 0.5 s internally, so we set 0.5 and sleep a bit longer.
        self.cache.set(("test", "expired"), "value", ttl=0.5, fingerprint="v:0")
        time.sleep(0.6)
        assert self.cache.get(("test", "expired")) is None

    # ------------------------------------------------------------------
    # Fingerprint / generation
    # ------------------------------------------------------------------

    def test_fingerprint_mismatch_returns_none(self) -> None:
        """If the entry was stored with a different fingerprint than the
        current generation produces, get() should return None."""
        self.cache.set(("fp",), "val", ttl=60.0, fingerprint="v:999")
        # Current generation is 0 → fingerprint will be "v:0" on lookup
        assert self.cache.get(("fp",)) is None

    def test_bump_generation_invalidates(self) -> None:
        """After bumping the cache generation, old entries become invisible
        because their fingerprint no longer matches."""
        self.cache.set(("test",), "value", ttl=60.0, fingerprint="v:0")
        assert self.cache.get(("test",)) == "value"

        new_gen = self.cache.bump_cache_generation()  # version → 1
        assert new_gen == 1
        # Old entry has fingerprint "v:0", but generation is now 1
        assert self.cache.get(("test",)) is None

    def test_bump_generation_returns_incremented(self) -> None:
        assert self.cache.bump_cache_generation() == 1
        assert self.cache.bump_cache_generation() == 2
        assert self.cache.cache_generation() == 2

    # ------------------------------------------------------------------
    # Domain invalidation
    # ------------------------------------------------------------------

    def test_invalidate_domains_removes_matching(self) -> None:
        self.cache.set(("dashboard", "stats"), {"val": 1}, ttl=60.0, fingerprint="v:0")
        self.cache.set(("sales", "total"), {"val": 2}, ttl=60.0, fingerprint="v:0")
        removed = self.cache.invalidate_domains("dashboard")
        assert removed >= 1
        # dashboard key gone; sales key also invalid because invalidate_domains bumps generation
        assert self.cache.get(("dashboard", "stats")) is None

    def test_invalidate_domains_multiple(self) -> None:
        self.cache.set(("a", "1"), 1, ttl=60.0, fingerprint="v:0")
        self.cache.set(("b", "2"), 2, ttl=60.0, fingerprint="v:0")
        self.cache.set(("c", "3"), 3, ttl=60.0, fingerprint="v:0")
        removed = self.cache.invalidate_domains("a", "b")
        assert removed >= 2

    def test_invalidate_empty_domain_is_noop(self) -> None:
        self.cache.set(("x",), 1, ttl=60.0, fingerprint="v:0")
        removed = self.cache.invalidate_domains("")
        # Empty domain should not match anything directly, but generation still bumps
        assert removed == 0

    # ------------------------------------------------------------------
    # LRU eviction
    # ------------------------------------------------------------------

    def test_lru_eviction(self) -> None:
        """Filling the cache beyond _MAX_ENTRIES should evict old entries."""
        from app.core.perf_cache import _MAX_ENTRIES

        for i in range(_MAX_ENTRIES + 100):
            self.cache.set(("test", f"key_{i}"), i, ttl=60.0, fingerprint="v:0")
        assert self.cache.entry_count() <= _MAX_ENTRIES

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def test_clear(self) -> None:
        self.cache.set(("a",), 1, ttl=60.0, fingerprint="v:0")
        self.cache.set(("b",), 2, ttl=60.0, fingerprint="v:0")
        self.cache.clear()
        assert self.cache.entry_count() == 0

    # ------------------------------------------------------------------
    # entry_count
    # ------------------------------------------------------------------

    def test_entry_count(self) -> None:
        assert self.cache.entry_count() == 0
        self.cache.set(("a",), 1, ttl=60.0, fingerprint="v:0")
        assert self.cache.entry_count() == 1
        self.cache.set(("b",), 2, ttl=60.0, fingerprint="v:0")
        assert self.cache.entry_count() == 2

    def test_entry_count_no_duplicates(self) -> None:
        """Setting the same key twice should not increase entry_count."""
        self.cache.set(("k",), "v1", ttl=60.0, fingerprint="v:0")
        self.cache.set(("k",), "v2", ttl=60.0, fingerprint="v:0")
        assert self.cache.entry_count() == 1

    # ------------------------------------------------------------------
    # cache_generation
    # ------------------------------------------------------------------

    def test_initial_generation_is_zero(self) -> None:
        assert self.cache.cache_generation() == 0
