from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AuthenticationRequiredError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
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


def handle_web_error_response(request: Request, message: str, status_code: int = 400):
    """Render a flash toast notification or fallback error page for HTML web requests.

    If the request originated from a form submission or user action (POST/PUT/DELETE/PATCH)
    or has a referer, flash a toast notification and redirect back to the referer so the user
    stays on their current screen without seeing a full error.html page.
    """
    referer = request.headers.get("referer")
    method = str(getattr(request, "method", "GET")).upper()
    is_mutation = method in ("POST", "PUT", "DELETE", "PATCH")

    # If it's a mutation (form action) or referer is present and different from current URL
    if referer and (is_mutation or (status_code in (400, 401, 403, 404, 409, 422) and referer != str(request.url))):
        from app.web.deps import flash
        from fastapi.responses import RedirectResponse

        try:
            flash(request, message, "danger")
        except Exception:
            pass
        return RedirectResponse(referer, status_code=303)

    from app.web.deps import template_context, templates

    return templates.TemplateResponse(
        "error.html",
        template_context(request, status_code=status_code, error_message=message),
        status_code=status_code,
    )


async def not_found_handler(request: Request, exc: NotFoundError):
    if not is_html_request(request):
        return JSONResponse(
            {
                "success": False,
                "error": {"code": exc.code, "message": exc.message, "resource": exc.resource, "id": str(exc.id)},
            },
            status_code=404,
        )
    return handle_web_error_response(request, exc.message, status_code=404)


async def validation_handler(request: Request, exc: ValidationError):
    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=422,
        )
    return handle_web_error_response(request, exc.message, status_code=422)


async def conflict_handler(request: Request, exc: ConflictError):
    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=409,
        )
    return handle_web_error_response(request, exc.message, status_code=409)


async def permission_handler(request: Request, exc: PermissionDeniedError):
    from app.core.request_state import get_state_value, set_state_value

    if get_state_value("request") is None:
        set_state_value("request", request)
    from app.core.permissions import permission_denied_response

    return permission_denied_response(exc.code)


async def auth_required_handler(request: Request, exc: AuthenticationRequiredError):
    from app.core.request_state import get_state_value, set_state_value

    if get_state_value("request") is None:
        set_state_value("request", request)
    from app.core.permissions import permission_denied_response

    return permission_denied_response(None)


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException):
    is_api = request.url.path.startswith("/api/") or not is_html_request(request)

    if is_api:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            code = detail.get("code") or ("not_found" if exc.status_code == 404 else "http_error")
            message = detail.get("message") or "HTTP Exception occurred"
            details = detail.get("details")
        else:
            code = "not_found" if exc.status_code == 404 else "http_error"
            message = str(detail) if detail else ("Ressource introuvable" if exc.status_code == 404 else "Erreur HTTP")
            details = None

        return JSONResponse(
            {"success": False, "error": {"code": code, "message": message, "details": details}},
            status_code=exc.status_code,
        )

    detail_msg = getattr(exc, "detail", None)
    if isinstance(detail_msg, dict):
        detail_msg = detail_msg.get("message") or str(detail_msg)
    elif not detail_msg:
        detail_msg = "Ressource introuvable" if exc.status_code == 404 else "Une erreur s'est produite."
    return handle_web_error_response(request, str(detail_msg), status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception):
    # Handle socket disconnects (client closed connection before response returned)
    if isinstance(exc, (ConnectionResetError, BrokenPipeError, OSError)):
        err_str = str(exc).lower()
        if "broken pipe" in err_str or "connection reset" in err_str or "errno 32" in err_str or "errno 104" in err_str:
            return JSONResponse({"status": "disconnected"}, status_code=200)

    if isinstance(exc, ValueError):
        if not is_html_request(request):
            return JSONResponse(
                {"success": False, "error": {"code": "invalid_value", "message": str(exc)}}, status_code=400
            )
        return handle_web_error_response(request, str(exc), status_code=400)

    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)

    err_msg = str(exc).lower()
    if (
        "foreign key" in err_msg
        or "violates foreign key constraint" in err_msg
        or "clé étrangère" in err_msg
        or "foreignkey" in err_msg
    ):
        friendly_msg = "Action impossible : cet élément est lié à d'autres opérations enregistrées dans le système et ne peut pas être modifié ou supprimé."
    elif (
        "unique constraint" in err_msg
        or "duplicate key" in err_msg
        or "clé dupliquée" in err_msg
        or "contrainte unique" in err_msg
        or "uniqueviolation" in err_msg
    ):
        friendly_msg = (
            "Action impossible : cette valeur existe déjà. Veuillez utiliser un nom ou un identifiant unique."
        )
    elif (
        "numeric value out of range" in err_msg
        or "valeur numérique en dehors des limites" in err_msg
        or "out of range" in err_msg
        or "numeric_value_out_of_range" in err_msg
    ):
        friendly_msg = (
            "Action impossible : un des montants ou quantités saisis dépasse les limites numériques autorisées."
        )
    elif (
        "operationalerror" in err_msg
        or "connection closed" in err_msg
        or "could not connect" in err_msg
        or "databaseerror" in err_msg
    ):
        friendly_msg = (
            "La connexion à la base de données PostgreSQL a été réinitialisée. Veuillez réessayer dans un instant."
        )
    else:
        friendly_msg = f"Une erreur interne inattendue s'est produite ({type(exc).__name__})."

    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": "internal_error", "message": friendly_msg}}, status_code=500
        )

    return handle_web_error_response(request, friendly_msg, status_code=500)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "valeur invalide")
        errors.append(f"{loc}: {msg}")
    friendly_msg = "Erreur de validation des données : " + ", ".join(errors)

    if not is_html_request(request):
        return JSONResponse(
            {"success": False, "error": {"code": "validation_error", "message": friendly_msg, "details": exc.errors()}},
            status_code=422,
        )

    return handle_web_error_response(request, friendly_msg, status_code=422)


def register_exception_handlers(app) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ValidationError, validation_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(PermissionDeniedError, permission_handler)
    app.add_exception_handler(AuthenticationRequiredError, auth_required_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
