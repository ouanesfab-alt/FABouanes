"""Module Catalogue — Gestion des matières premières, produits finis et recettes."""

from app.core.registry import register
from app.modules.base import ModuleBase


class CatalogModule(ModuleBase):
    @property
    def name(self) -> str:
        return "catalog"

    @property
    def label(self) -> str:
        return "Catalogue"

    @property
    def icon(self) -> str:
        return "bi-box"

    @property
    def nav_order(self) -> int:
        return 50

    @property
    def web_router(self):
        from app.modules.catalog.web import router

        return router

    @property
    def permissions(self) -> list[str]:
        return ["catalog.read", "catalog.write", "catalog.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["catalog.read", "catalog.write", "catalog.delete"],
            "operator": ["catalog.read"],
        }


# Registration
register(CatalogModule())
