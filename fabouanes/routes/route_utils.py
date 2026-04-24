from __future__ import annotations

from collections.abc import Iterable
from functools import wraps

from fabouanes.fastapi_compat import current_app, flash, g, jsonify
from fabouanes.domain.exceptions import FabouanesError


def bind_route(app, rule: str, endpoint: str, view_func, methods: Iterable[str]) -> None:
    if rule.startswith("/api/"):

        @wraps(view_func)
        def api_wrapped(*args, **kwargs):
            try:
                return view_func(*args, **kwargs)
            except FabouanesError as exc:
                return jsonify({"error": {"code": "application_error", "message": str(exc)}}), 400
            except Exception as exc:
                try:
                    request_id = str(getattr(g, "request_id", "") or "")
                except Exception:
                    request_id = ""
                current_app.logger.exception("Unhandled API route exception: %s", exc)
                return jsonify({"error": {"code": "internal_error", "message": "Erreur interne.", "request_id": request_id}}), 500

        view = api_wrapped
    else:
        view = view_func
    if endpoint in app.view_functions:
        app.view_functions[endpoint] = view
        return
    app.add_url_rule(rule, endpoint=endpoint, view_func=view, methods=list(methods))


def flash_route_exception(exc: Exception, fallback_message: str = "Une erreur inattendue est survenue.") -> None:
    if isinstance(exc, (ValueError, FabouanesError)):
        flash(str(exc), "danger")
        return
    current_app.logger.exception("Unhandled error while serving a FABOuanes route")
    flash(fallback_message, "danger")
