"""Module Utilisateurs — Authentification, rôles et sécurité."""

from __future__ import annotations

from app.core.registry import register
from app.modules.base import ModuleBase


class UsersModule(ModuleBase):
    @property
    def name(self) -> str:
        return "users"

    @property
    def label(self) -> str:
        return "Utilisateurs"

    @property
    def icon(self) -> str:
        return "bi-shield-lock"

    @property
    def nav_order(self) -> int:
        return 110

    @property
    def permissions(self) -> list[str]:
        return ["admin.users", "users.read", "users.write"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "admin": ["admin.users", "users.read", "users.write"],
            "manager": ["users.read"],
            "operator": [],
        }


# Registration
register(UsersModule())
