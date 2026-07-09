"""Module Clients — Gestion des partenaires clients."""
from app.modules.base import ModuleBase
from app.modules.clients.web import router as web_router
from app.core.registry import register
from app.modules.clients.schema import TABLES

class ClientsModule(ModuleBase):
    @property
    def name(self) -> str:
        return "clients"

    @property
    def label(self) -> str:
        return "Clients"

    @property
    def icon(self) -> str:
        return "bi-people"

    @property
    def nav_order(self) -> int:
        return 40

    @property
    def web_router(self):
        return web_router

    @property
    def schema_sql(self) -> list[str]:
        return TABLES

    @property
    def permissions(self) -> list[str]:
        return ["contacts.read", "contacts.write", "contacts.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["contacts.read", "contacts.write", "contacts.delete"],
            "operator": ["contacts.read"],
        }

# Registration
register(ClientsModule())
