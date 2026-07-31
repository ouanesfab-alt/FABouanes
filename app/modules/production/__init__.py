"""Module Production — Gestion de la transformation et fabrication de produits."""
from __future__ import annotations

from app.core.registry import register
from app.core.schema.production import SCHEMA_PRODUCTION
from app.modules.base import ModuleBase


class ProductionModule(ModuleBase):
    @property
    def name(self) -> str:
        return "production"

    @property
    def label(self) -> str:
        return "Production"

    @property
    def icon(self) -> str:
        return "bi-gear-wide-connected"

    @property
    def nav_order(self) -> int:
        return 70

    @property
    def schema_sql(self) -> list[str]:
        return [SCHEMA_PRODUCTION]

    @property
    def permissions(self) -> list[str]:
        return ["production.read", "production.write", "production.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["production.read", "production.write", "production.delete"],
            "operator": ["production.read", "production.write"],
        }

# Automatic discovery registration
register(ProductionModule())
