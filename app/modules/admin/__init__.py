"""Module Administration — Paramètres, sauvegardes, journaux et maintenance système."""

from __future__ import annotations

from app.core.registry import register
from app.modules.base import ModuleBase


class AdminModule(ModuleBase):
    @property
    def name(self) -> str:
        return "admin"

    @property
    def label(self) -> str:
        return "Administration"

    @property
    def icon(self) -> str:
        return "bi-gear"

    @property
    def nav_order(self) -> int:
        return 120

    @property
    def permissions(self) -> list[str]:
        return ["admin.users", "admin.system", "admin.backup", "admin.audit"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "admin": ["admin.users", "admin.system", "admin.backup", "admin.audit"],
            "manager": [],
            "operator": [],
        }


# Registration
register(AdminModule())
