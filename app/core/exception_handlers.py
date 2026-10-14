# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour exception_handlers.
Toutes les fonctions sont désormais hébergées dans app.web.exception_handlers
afin de préserver le découplage Clean Architecture (Core ne dépend plus de Web).
"""

from __future__ import annotations

from app.web.exception_handlers import (
    auth_required_handler,
    conflict_handler,
    http_exception_handler,
    is_html_request,
    not_found_handler,
    permission_handler,
    register_exception_handlers,
    unhandled_exception_handler,
    validation_error_handler,
    validation_handler,
)

__all__ = [
    "is_html_request",
    "not_found_handler",
    "validation_handler",
    "conflict_handler",
    "permission_handler",
    "auth_required_handler",
    "http_exception_handler",
    "unhandled_exception_handler",
    "validation_error_handler",
    "register_exception_handlers",
]
