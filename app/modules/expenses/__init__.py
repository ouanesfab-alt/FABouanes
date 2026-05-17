"""Module Dépenses & Charges — Suivi des frais de l'entreprise."""
from app.modules.base import ModuleBase
from app.modules.expenses.web import router as web_router
from app.core.registry import ModuleDescriptor, register
from app.modules.expenses.schema import TABLES

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
        return web_router

    @property
    def schema_sql(self) -> list[str]:
        return TABLES

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

