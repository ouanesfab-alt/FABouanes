from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings, validate_single_worker_runtime
from app.core.runtime_paths import ensure_runtime_dirs
from app.core.logging import configure_logging
from app.core.audit import start_audit_worker, stop_audit_worker
from app.core.database import bootstrap_and_migrate
from app.core.registry import get_enabled_modules
from app.core.db_helpers import execute_db

logger = logging.getLogger("fabouanes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_single_worker_runtime()
    ensure_runtime_dirs()
    configure_logging()
    start_audit_worker()

    # Initialize Observability (OpenTelemetry & structlog)
    try:
        from app.core.observability import setup_observability, instrument_app
        setup_observability("fabouanes")
        instrument_app(app)
    except Exception as exc:
        logger.warning("Failed to initialize observability: %s", exc)

    await asyncio.to_thread(bootstrap_and_migrate)

    # Bootstrap module schemas (CREATE TABLE IF NOT EXISTS)
    for module in get_enabled_modules():
        for sql in module.schema_sql:
            try:
                await asyncio.to_thread(execute_db, sql)
            except Exception:
                logger.warning("Module schema error for %s: %s", module.name, sql[:80])

    logger.info("Modules loaded: %s", [m.name for m in get_enabled_modules()])

    # Start background worker now that all DB tables and staging schemas are fully ready
    try:
        from app.core.worker import start_worker
        start_worker()
    except Exception as e:
        logger.warning("Erreur au démarrage du worker des tâches de fond: %s", e)

    from app.services.backup_service import start_background_services
    start_background_services(app)
    try:
        from app.core.events import startup as events_startup
        events_startup()
    except Exception as e:
        logger.warning("Erreur au démarrage du service d'événements: %s", e)

    try:
        from app.core.websockets import startup as ws_startup
        ws_startup()
    except Exception as e:
        logger.warning("Erreur au démarrage du service WebSockets: %s", e)

    # Pre-load critical dashboard data so first request is instant
    try:
        from app.core.perf_cache import warm_cache
        await warm_cache()
    except Exception:
        logger.warning("Cache warming skipped", exc_info=True)

    logger.info(
        "FABOuanes started | env=%s desktop=%s host=%s port=%s modules=%s",
        settings.env,
        settings.desktop_mode,
        settings.host,
        settings.port,
        [m.name for m in get_enabled_modules()],
    )

    try:
        yield
    finally:
        logger.info("Arrêt en cours, arrêt des services...")
        try:
            await stop_audit_worker()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du worker d'audit: %s", e)

        try:
            from app.core.worker import stop_worker
            stop_worker()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du worker des tâches de fond: %s", e)

        try:
            from app.core.events import shutdown as events_shutdown
            events_shutdown()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du service d'événements: %s", e)

        try:
            from app.core.websockets import shutdown as ws_shutdown
            ws_shutdown()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du service WebSockets: %s", e)

        try:
            from app.services.backup_service import shutdown_background_services
            shutdown_background_services(app)
        except Exception as e:
            logger.warning("Erreur pendant le shutdown: %s", e)

        try:
            from app.modules.assistant.service import close_http_clients
            await close_http_clients()
        except Exception as e:
            logger.warning("Erreur lors de la fermeture des clients HTTP Sabrina: %s", e)

        try:
            from app.core.db_helpers import db_manager
            db_manager.shutdown()
        except Exception as e:
            logger.warning("Erreur lors de l'arrêt du db_manager: %s", e)

        try:
            from app.core.async_db import close_async_engine
            await close_async_engine()
        except Exception as e:
            logger.warning("Erreur lors de la fermeture du moteur asynchrone: %s", e)
        logger.info("Shutdown terminé.")
