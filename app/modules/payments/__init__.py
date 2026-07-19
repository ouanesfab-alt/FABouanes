"""Module Règlements — Gestion des versements et avances clients."""
from app.modules.base import ModuleBase
from app.modules.payments.web import router as web_router
from app.core.registry import register

class PaymentsModule(ModuleBase):
    @property
    def name(self) -> str:
        return "payments"

    @property
    def label(self) -> str:
        return "Paiements"

    @property
    def icon(self) -> str:
        return "bi-cash-coin"

    @property
    def nav_order(self) -> int:
        return 80

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
register(PaymentsModule())
