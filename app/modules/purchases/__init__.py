"""Module Achats — Gestion des approvisionnements et des bons d'achat."""
from app.modules.base import ModuleBase
from app.core.registry import register

class PurchasesModule(ModuleBase):
    @property
    def name(self) -> str:
        return "purchases"

    @property
    def label(self) -> str:
        return "Achats"

    @property
    def icon(self) -> str:
        return "bi-bag"

    @property
    def nav_order(self) -> int:
        return 70

    @property
    def web_router(self):
        from app.modules.purchases.api.web import router as web_router
        return web_router

    @property
    def api_router(self):
        from app.modules.purchases.api.endpoints import router as api_router
        return api_router

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
register(PurchasesModule())
