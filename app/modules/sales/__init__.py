"""Module Ventes — Gestion des factures et lignes de vente."""
from app.modules.base import ModuleBase
from app.modules.sales.web import router as web_router
from app.core.registry import register

class SalesModule(ModuleBase):
    @property
    def name(self) -> str:
        return "sales"

    @property
    def label(self) -> str:
        return "Ventes"

    @property
    def icon(self) -> str:
        return "bi-cart"

    @property
    def nav_order(self) -> int:
        return 60

    @property
    def web_router(self):
        return web_router

    @property
    def permissions(self) -> list[str]:
        return ["operations.read", "operations.write", "operations.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["operations.read", "operations.write", "operations.delete"],
            "operator": ["operations.read"],
        }

# Registration
register(SalesModule())
