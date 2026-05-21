from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi.errors import RateLimitExceeded
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionDeniedError,
    AuthenticationRequiredError,
)

logger = logging.getLogger("fabouanes")


class CachedStaticFiles(StaticFiles):
    def is_not_modified(self, response_headers, request_headers) -> bool:
        return super().is_not_modified(response_headers, request_headers)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # Cache statics for 1 year; versioning is handled via ?v= query parameter in templates
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

from app.api.router import router as api_router
from app.core.config import settings, validate_single_worker_runtime
from app.core.database import bootstrap_and_migrate, create_request_connection
from app.core.db_access import execute_db
from app.core.logging import configure_logging
from app.core.registry import discover_modules, get_enabled_modules, mount_api_routes, mount_web_routes
from app.core.request_state import push_request_state, reset_request_state, set_state_value
from app.core.runtime_paths import ensure_runtime_dirs, paths
from app.core.security import security_headers
from app.services.backup_service import start_background_services
from app.web.deps import ensure_csrf_token, load_user_from_session
from app.web.router import router as web_router
from app.core.rate_limit import limiter, rate_limit_exceeded_handler



@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_single_worker_runtime()
    ensure_runtime_dirs()
    configure_logging()
    bootstrap_and_migrate()

    # Bootstrap module schemas (CREATE TABLE IF NOT EXISTS)
    for module in get_enabled_modules():
        for sql in module.schema_sql:
            try:
                execute_db(sql)
            except Exception:
                logger.warning("Module schema error for %s: %s", module.name, sql[:80])

    logger.info("Modules loaded: %s", [m.name for m in get_enabled_modules()])

    start_background_services(app)
    try:
        yield
    finally:
        logger.info("Arrêt en cours, attente du scheduler...")
        try:
            from app.services.backup_service import shutdown_background_services
            shutdown_background_services(app)
        except Exception as e:
            logger.warning("Erreur pendant le shutdown: %s", e)
        logger.info("Shutdown terminé.")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static/"):
            response = await call_next(request)
            return security_headers(response)

        # Inject transparent global XSS sanitization on request.form for form types only
        content_type = request.headers.get("content-type", "")
        is_form = "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type

        if is_form:
            original_form = request.form
            async def sanitized_form():
                form_data = await original_form()
                from app.core.sanitizer import sanitize_string
                from starlette.datastructures import FormData, UploadFile
                cleaned_items = []
                for k, v in form_data.multi_items():
                    if isinstance(v, UploadFile):
                        cleaned_items.append((k, v))
                    elif "password" in k.lower():
                        cleaned_items.append((k, v))
                    else:
                        cleaned_items.append((k, sanitize_string(v)))
                return FormData(cleaned_items)
            request.form = sanitized_form


        db = create_request_connection()
        token = push_request_state(
            request=request,
            db=db,
            session=request.session,
            request_id=secrets.token_hex(12),
            audit_source="api" if request.url.path.startswith("/api/v1/") else "web",
            user=None,
            g=SimpleNamespace(user=None),
        )
        try:
            ensure_csrf_token(request)
            user = load_user_from_session(request)
            request.state.user = user
            set_state_value("user", user)
            set_state_value("g", SimpleNamespace(user=user))
            response = await call_next(request)
        finally:
            try:
                db.close()
            except Exception:
                pass
            reset_request_state(token)
        return security_headers(response)


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


def is_html_request(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/api/"):
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return False
    return True


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": exc.code, "message": exc.message, "resource": exc.resource, "id": str(exc.id)}},
            status_code=404
        )
    from app.web.deps import template_context, templates
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=404, error_message=exc.message),
        status_code=404
    )

@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=422
        )
    from app.web.deps import template_context, templates
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=422, error_message=exc.message),
        status_code=422
    )

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=409
        )
    from app.web.deps import template_context, templates
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=409, error_message=exc.message),
        status_code=409
    )

@app.exception_handler(PermissionDeniedError)
async def permission_handler(request: Request, exc: PermissionDeniedError):
    from app.core.permissions import permission_denied_response
    return permission_denied_response(exc.code)

@app.exception_handler(AuthenticationRequiredError)
async def auth_required_handler(request: Request, exc: AuthenticationRequiredError):
    from app.core.permissions import permission_denied_response
    return permission_denied_response(None)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        if not is_html_request(request):
            return JSONResponse({"success": False, "error": {"code": "http_error", "message": exc.detail}}, status_code=exc.status_code)
        from app.web.deps import template_context, templates
        return templates.TemplateResponse(
            "error.html",
            template_context(request, status_code=exc.status_code, error_message=exc.detail),
            status_code=exc.status_code
        )
        
    if isinstance(exc, ValueError):
        if not is_html_request(request):
            return JSONResponse({"success": False, "error": {"code": "invalid_value", "message": str(exc)}}, status_code=400)
        from app.web.deps import template_context, templates
        return templates.TemplateResponse(
            "error.html",
            template_context(request, status_code=400, error_message=str(exc)),
            status_code=400
        )
    
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    
    err_msg = str(exc)
    if "foreign key" in err_msg.lower() or "violates foreign key constraint" in err_msg.lower():
        friendly_msg = "Action impossible : cet élément est lié à d'autres opérations enregistrées dans le système et ne peut pas être modifié ou supprimé."
    elif "unique constraint" in err_msg.lower() or "duplicate key" in err_msg.lower():
        friendly_msg = "Action impossible : cette valeur existe déjà. Veuillez utiliser un nom ou un identifiant unique."
    elif "numeric value out of range" in err_msg.lower():
        friendly_msg = "Action impossible : un des montants ou quantités saisis dépasse les limites numériques autorisées."
    else:
        friendly_msg = f"Une erreur interne inattendue s'est produite ({type(exc).__name__})."

    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": "internal_error", "message": friendly_msg}},
            status_code=500
        )
    
    from app.web.deps import template_context, templates
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=500, error_message=friendly_msg),
        status_code=500
    )




@app.get("/health")
async def health_check():
    import shutil
    import time
    from app.core.database import healthcheck
    from app.services.backup_service import BACKGROUND_STATE

    checks: dict[str, str] = {"db": "ok", "scheduler": "ok", "disk": "ok"}
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

    status = "ok" if all(v == "ok" for k, v in checks.items() if k not in ["disk_free_mb", "last_run_age_s", "last_backup_age_h"]) else "degraded"
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


app.mount("/static", CachedStaticFiles(directory=str(paths.static_dir)), name="static")
app.include_router(web_router)
app.include_router(api_router)
