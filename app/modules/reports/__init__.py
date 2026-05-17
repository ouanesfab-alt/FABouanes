"""Module Rapports & Statistiques — Tableaux de bord analytiques."""
from app.modules.base import ModuleBase
from app.modules.reports.web import router as web_router
from app.core.registry import ModuleDescriptor, register

class ReportsModule(ModuleBase):
    @property
    def name(self) -> str:
        return "reports"
    
    @property
    def label(self) -> str:
        return "Rapports"
    
    @property
    def icon(self) -> str:
        return "bi-bar-chart-line"

    @property
    def nav_order(self) -> int:
        return 50

    @property
    def web_router(self):
        return web_router

    @property
    def permissions(self) -> list[str]:
        return ["reports.read"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["reports.read"],
            "operator": ["reports.read"],
        }

# Registration
register(ReportsModule())

