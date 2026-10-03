from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.async_db import close_async_engine
from app.core.audit import start_audit_worker, stop_audit_worker
from app.core.config import settings, validate_security_runtime, validate_single_worker_runtime
from app.core.database import bootstrap_and_migrate
from app.core.db_helpers import db_manager, execute_db  # noqa: F401
from app.core.events import shutdown as events_shutdown, startup as events_startup
from app.core.logging import configure_logging
from app.core.middleware import preload_static_files
from app.core.observability import instrument_app, setup_observability
from app.core.perf_cache import warm_cache
from app.core.registry import get_enabled_modules
from app.core.runtime_paths import ensure_runtime_dirs, paths
from app.core.websockets import shutdown as ws_shutdown, startup as ws_startup
from app.core.worker import start_worker, stop_worker
from app.modules.assistant.service import close_http_clients
from app.services.backup_service import shutdown_background_services, start_background_services
from app.web.deps import preload_templates

logger = logging.getLogger("fabouanes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_single_worker_runtime()
    validate_security_runtime()
    ensure_runtime_dirs()
    configure_logging()
    start_audit_worker()

    # Initialize Observability (OpenTelemetry & structlog)
    try:
        setup_observability("fabouanes")
        instrument_app(app)
    except Exception as exc:
        logger.warning("Failed to initialize observability: %s", exc)

    await asyncio.to_thread(bootstrap_and_migrate)

    logger.info("Modules loaded: %s", [m.name for m in get_enabled_modules()])

    # Start background worker now that all DB tables and staging schemas are fully ready
    try:
        start_worker()
    except Exception as e:
        logger.warning("Erreur au démarrage du worker des tâches de fond: %s", e)

    start_background_services(app)
    try:
        events_startup()
    except Exception as e:
        logger.warning("Erreur au démarrage du service d'événements: %s", e)

    try:
        ws_startup()
    except Exception as e:
        logger.warning("Erreur au démarrage du service WebSockets: %s", e)

    # Pre-load entire application into RAM (Static Assets, Jinja2 Templates, and Data Caches)
    try:
        static_count = preload_static_files(paths.static_dir)
        logger.info("RAM Static Cache: %d assets loaded into memory.", static_count)
    except Exception as e:
        logger.warning("Erreur préchargement des fichiers statiques en RAM: %s", e)

    try:
        template_count = preload_templates()
        logger.info("RAM Template Cache: %d templates pre-compiled into memory.", template_count)
    except Exception as e:
        logger.warning("Erreur pré-compilation des templates HTML en RAM: %s", e)

    # Pre-load critical dashboard data asynchronously in background
    try:
        asyncio.create_task(warm_cache())
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
            stop_worker()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du worker des tâches de fond: %s", e)

        try:
            events_shutdown()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du service d'événements: %s", e)

        try:
            ws_shutdown()
        except Exception as e:
            logger.warning("Erreur à l'arrêt du service WebSockets: %s", e)

        try:
            shutdown_background_services(app)
        except Exception as e:
            logger.warning("Erreur pendant le shutdown: %s", e)

        try:
            await close_http_clients()
        except Exception as e:
            logger.warning("Erreur lors de la fermeture des clients HTTP Sabrina: %s", e)

        try:
            db_manager.shutdown()
        except Exception as e:
            logger.warning("Erreur lors de l'arrêt du db_manager: %s", e)

        try:
            await close_async_engine()
        except Exception as e:
            logger.warning("Erreur lors de la fermeture du moteur asynchrone: %s", e)
        logger.info("Shutdown terminé.")
