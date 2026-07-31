# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour production_pages.
Le APIRouter est désormais hébergé dans app.modules.production.web.
"""
from __future__ import annotations

from app.modules.production.web import (
    router,
    parse_production_form,
    production_page,
    production_submit,
    new_production_page,
    new_production_submit,
    delete_production,
)

__all__ = [
    "router",
    "parse_production_form",
    "production_page",
    "production_submit",
    "new_production_page",
    "new_production_submit",
    "delete_production",
]
