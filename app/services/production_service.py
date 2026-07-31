# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour production_service.
Toutes les fonctions sont désormais hébergées dans app.modules.production.service.
"""
from __future__ import annotations

from app.modules.production.service import (
    create_production_from_form,
    delete_production_by_id,
    new_production_context,
    productions_context,
)

__all__ = [
    "productions_context",
    "new_production_context",
    "create_production_from_form",
    "delete_production_by_id",
]
