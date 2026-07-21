from __future__ import annotations

import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionDeniedError,
    AuthenticationRequiredError,
)

logger = logging.getLogger("fabouanes")


def is_html_request(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/api/"):
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return False
    return True


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


async def permission_handler(request: Request, exc: PermissionDeniedError):
    from app.core.permissions import permission_denied_response
    return permission_denied_response(exc.code)


async def auth_required_handler(request: Request, exc: AuthenticationRequiredError):
    from app.core.permissions import permission_denied_response
    return permission_denied_response(None)


async def http_exception_handler(request: Request, exc: HTTPException):
    is_api = request.url.path.startswith("/api/") or not is_html_request(request)

    if is_api:
        detail = exc.detail
        if isinstance(detail, dict):
            code = detail.get("code") or "http_error"
            message = detail.get("message") or "HTTP Exception occurred"
            details = detail.get("details")
        else:
            code = "http_error"
            message = str(detail)
            details = None

        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details
                }
            },
            status_code=exc.status_code
        )

    from app.web.deps import template_context, templates
    detail_msg = exc.detail
    if isinstance(detail_msg, dict):
        detail_msg = detail_msg.get("message") or str(detail_msg)
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=exc.status_code, error_message=detail_msg),
        status_code=exc.status_code
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
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

    err_msg = str(exc).lower()
    if "foreign key" in err_msg or "violates foreign key constraint" in err_msg or "clé étrangère" in err_msg or "foreignkey" in err_msg:
        friendly_msg = "Action impossible : cet élément est lié à d'autres opérations enregistrées dans le système et ne peut pas être modifié ou supprimé."
    elif "unique constraint" in err_msg or "duplicate key" in err_msg or "clé dupliquée" in err_msg or "contrainte unique" in err_msg or "uniqueviolation" in err_msg:
        friendly_msg = "Action impossible : cette valeur existe déjà. Veuillez utiliser un nom ou un identifiant unique."
    elif "numeric value out of range" in err_msg or "valeur numérique en dehors des limites" in err_msg or "out of range" in err_msg or "numeric_value_out_of_range" in err_msg:
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



from fastapi.exceptions import RequestValidationError

async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "valeur invalide")
        errors.append(f"{loc}: {msg}")
    friendly_msg = "Erreur de validation des données : " + ", ".join(errors)

    if not is_html_request(request):
        return JSONResponse(
            {
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": friendly_msg,
                    "details": exc.errors()
                }
            },
            status_code=422
        )

    from app.web.deps import template_context, templates
    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=422, error_message=friendly_msg),
        status_code=422
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ValidationError, validation_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(PermissionDeniedError, permission_handler)
    app.add_exception_handler(AuthenticationRequiredError, auth_required_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

