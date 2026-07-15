"""Module Production — Gestion de la production d'aliments et matières consommées."""
from app.modules.base import ModuleBase
from app.core.registry import register

class ProductionModule(ModuleBase):
    @property
    def name(self) -> str:
        return "production"

    @property
    def label(self) -> str:
        return "Production"

    @property
    def icon(self) -> str:
        return "bi-tools"

    @property
    def nav_order(self) -> int:
        return 70

    @property
    def web_router(self):
        from app.modules.production.api.web import router as web_router
        return web_router

    @property
    def api_router(self):
        from app.modules.production.api.endpoints import router as api_router
        return api_router

    @property
    def permissions(self) -> list[str]:
        return ["production.read", "production.write", "production.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["production.read", "production.write", "production.delete"],
            "operator": ["production.read"],
        }

# Registration
register(ProductionModule())
