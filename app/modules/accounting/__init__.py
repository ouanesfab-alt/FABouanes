"""Module de Comptabilité Système Comptable Financier (SCF Algérie)."""
from __future__ import annotations

from app.core.registry import register
from app.modules.accounting.web import router as web_router
from app.modules.base import ModuleBase


class AccountingModule(ModuleBase):
    @property
    def name(self) -> str:
        return "accounting"

    @property
    def label(self) -> str:
        return "Comptabilité SCF"

    @property
    def icon(self) -> str:
        return "bi-calculator"

    @property
    def nav_order(self) -> int:
        return 90

    @property
    def web_router(self):
        return web_router

    @property
    def permissions(self) -> list[str]:
        return ["accounting.read"]

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        return {
            "manager": ["accounting.read"],
            "operator": [],
        }


# Registration
register(AccountingModule())
