"""Tests unitaires pour app/core/lifespan.py (lot D3)."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown():
    from app.core.lifespan import lifespan

    app = FastAPI()

    with patch("app.core.lifespan.validate_single_worker_runtime"), \
         patch("app.core.lifespan.ensure_runtime_dirs"), \
         patch("app.core.lifespan.configure_logging"), \
         patch("app.core.lifespan.start_audit_worker"), \
         patch("app.core.lifespan.stop_audit_worker", new_callable=AsyncMock), \
         patch("app.core.lifespan.bootstrap_and_migrate"), \
         patch("app.core.lifespan.execute_db"), \
         patch("app.core.lifespan.get_enabled_modules", return_value=[]), \
         patch("app.services.backup_service.start_background_services"), \
         patch("app.services.backup_service.shutdown_background_services"):

        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_error_resilience():
    from app.core.lifespan import lifespan

    app = FastAPI()

    with patch("app.core.lifespan.validate_single_worker_runtime"), \
         patch("app.core.lifespan.ensure_runtime_dirs"), \
         patch("app.core.lifespan.configure_logging"), \
         patch("app.core.lifespan.start_audit_worker"), \
         patch("app.core.lifespan.stop_audit_worker", side_effect=RuntimeError("stop fail")), \
         patch("app.core.lifespan.bootstrap_and_migrate"), \
         patch("app.core.lifespan.execute_db"), \
         patch("app.core.lifespan.get_enabled_modules", return_value=[]), \
         patch("app.services.backup_service.start_background_services"), \
         patch("app.services.backup_service.shutdown_background_services", side_effect=RuntimeError("shutdown fail")):

        async with lifespan(app):
            pass
