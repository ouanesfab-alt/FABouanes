from __future__ import annotations

from collections.abc import Iterable

from flask import current_app, flash
from fabouanes.domain.exceptions import FabouanesError


def bind_route(app, rule: str, endpoint: str, view_func, methods: Iterable[str]) -> None:
    if endpoint in app.view_functions:
        app.view_functions[endpoint] = view_func
        return
    app.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=list(methods))


def flash_route_exception(exc: Exception, fallback_message: str = "Une erreur inattendue est survenue.") -> None:
    if isinstance(exc, (ValueError, FabouanesError)):
        flash(str(exc), "danger")
        return
    current_app.logger.exception("Unhandled error while serving a FABOuanes route")
    flash(fallback_message, "danger")
