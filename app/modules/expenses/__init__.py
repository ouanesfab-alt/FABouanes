"""Module Dépenses & Charges — Suivi des frais de l'entreprise."""
from app.modules.base import ModuleBase
from app.core.registry import register

class ExpensesModule(ModuleBase):
    @property
    def name(self) -> str:
        return "expenses"

    @property
    def label(self) -> str:
        return "Dépenses"

    @property
    def icon(self) -> str:
        return "bi-wallet2"

    @property
    def nav_order(self) -> int:
        return 45

    @property
    def web_router(self):
        from app.modules.expenses.api.web import router as web_router
        return web_router

    @property
    def api_router(self):
        from app.modules.expenses.api.endpoints import router as api_router
        return api_router

    @property
    def permissions(self) -> list[str]:
        return ["expenses.read", "expenses.write", "expenses.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["expenses.read", "expenses.write", "expenses.delete"],
            "operator": ["expenses.read"],
        }

# Registration
register(ExpensesModule())
