"""Unit-test configuration.

This conftest sets the minimal environment variables needed so that
``app.core.config`` can be imported without a running database.
It MUST be loaded *before* any app imports happen.

Run unit tests with:
    pytest tests/unit/ -v --no-cov --override-ini="confcutdir=tests/unit"
"""
from __future__ import annotations

import os

# Prevent app.core.config from raising "DATABASE_URL required"
os.environ.setdefault("DATABASE_URL", "postgresql://unit:unit@localhost:5432/unit_test")
os.environ.setdefault("SECRET_KEY", "unit-test-secret-key-not-real")
os.environ.setdefault("FASTAPI_ENV", "test")
os.environ.setdefault("FAB_DISABLE_BACKGROUND_JOBS", "1")
os.environ.setdefault("FAB_DESKTOP", "0")
