from __future__ import annotations

import shutil
import time
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.middleware import RequestContextMiddleware, CachedStaticFiles
from app.core.exception_handlers import register_exception_handlers
from app.core.timeout_middleware import RequestTimeoutMiddleware
from app.core.registry import discover_modules, mount_api_routes, mount_web_routes
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.runtime_paths import paths
from app.api.router import router as api_router
from app.web.router import router as web_router
from app.core.database import healthcheck
from app.services.backup_service import BACKGROUND_STATE
from app.version import APP_VERSION

logger = logging.getLogger("fabouanes")

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

Instrumentator().instrument(app).expose(app)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="fabouanes_session",
    same_site="lax",
    https_only=settings.session_cookie_secure,
    max_age=settings.session_max_age,
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RequestTimeoutMiddleware)

register_exception_handlers(app)


@app.get("/health")
@app.get("/readiness")
async def health_check():
    checks: dict[str, str] = {"db": "ok", "scheduler": "ok", "disk": "ok", "version": APP_VERSION}
    now = time.time()

    # Database connectivity
    try:
        await asyncio.wait_for(asyncio.to_thread(healthcheck), timeout=3.0)
    except asyncio.TimeoutError:
        checks["db"] = "timeout"
    except Exception:
        checks["db"] = "error"

    # Backup scheduler status
    last_run = BACKGROUND_STATE.get("last_run_ts", 0)
    last_backup = BACKGROUND_STATE.get("last_backup_ts", 0)

    if not BACKGROUND_STATE.get("started"):
        checks["scheduler"] = "stopped"
    elif last_run > 0 and (now - last_run) > 300: # 5 minutes threshold
        checks["scheduler"] = "stalled"

    if last_run > 0:
        checks["last_run_age_s"] = str(int(now - last_run))
    if last_backup > 0:
        checks["last_backup_age_h"] = str(round((now - last_backup) / 3600, 1))

    # Disk space (warn if < 100 MB free)
    try:
        usage = shutil.disk_usage(str(settings.app_data_dir))
        free_mb = usage.free / (1024 * 1024)
        checks["disk_free_mb"] = str(int(free_mb))
        if free_mb < 100:
            checks["disk"] = "low"
    except Exception:
        checks["disk"] = "unknown"

    # Cache and Performance queue stats
    try:
        from app.core.perf_cache import cache_entry_count
        checks["cache_entries"] = str(cache_entry_count())
    except Exception:
        checks["cache_entries"] = "unknown"

    try:
        from app.core.db_helpers import db_manager
        checks["perf_queue_size"] = str(db_manager.pending_performance_event_count())
    except Exception:
        checks["perf_queue_size"] = "unknown"

    status = "ok" if all(v == "ok" for k, v in checks.items() if k not in ["disk_free_mb", "last_run_age_s", "last_backup_age_h", "version", "cache_entries", "perf_queue_size"]) else "degraded"
    code = 200 if status == "ok" else 503
    return JSONResponse({"status": status, **checks}, status_code=code)


# ── Auto-discover feature modules ──
try:
    modules_dir = Path(__file__).resolve().parent / "modules"
    discover_modules(modules_dir)
    mount_web_routes(web_router)
    mount_api_routes(api_router)
except Exception as e:
    logger.critical("Erreur critique lors de la decouverte/montage des modules: %s", e, exc_info=True)


@app.get("/api/version")
@app.get("/api/v1/version")
async def get_version():
    from app.core.registry import get_enabled_modules
    from app.version import APP_VERSION
    return {
        "version": APP_VERSION,
        "app": "FABOuanes",
        "env": settings.env,
        "modules": [m.name for m in get_enabled_modules()],
    }


app.mount("/static", CachedStaticFiles(directory=str(paths.static_dir)), name="static")
app.include_router(web_router)
app.include_router(api_router)
