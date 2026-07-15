"""Module Users — Gestion des comptes utilisateurs de l'application."""
from app.modules.base import ModuleBase
from app.core.registry import register


class UsersModule(ModuleBase):
    @property
    def name(self) -> str:
        return "users"

    @property
    def label(self) -> str:
        return "Utilisateurs"

    @property
    def icon(self) -> str:
        return "bi-people"

    @property
    def nav_order(self) -> int:
        return 90

    @property
    def permissions(self) -> list[str]:
        return ["admin.read", "admin.write", "admin.delete"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "admin": ["admin.read", "admin.write", "admin.delete"],
        }


# Registration
register(UsersModule())
