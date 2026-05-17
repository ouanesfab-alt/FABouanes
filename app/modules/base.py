from __future__ import annotations

from abc import ABC, abstractmethod
from fastapi import APIRouter

class ModuleBase(ABC):
    """
    Abstract base class for all application modules.
    Ensures a consistent structure for routes and metadata.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Internal unique name of the module."""
        pass

    @property
    def label(self) -> str:
        """Display label for the module."""
        return self.name.capitalize()

    @property
    def icon(self) -> str:
        """Bootstrap icon name."""
        return "bi-box"

    @property
    def nav_order(self) -> int:
        """Navigation order."""
        return 100

    @property
    def web_router(self) -> APIRouter | None:
        """Web (HTML) router."""
        return None

    @property
    def api_router(self) -> APIRouter | None:
        """API (REST) router."""
        return None

    @property
    def schema_sql(self) -> list[str]:
        """SQL schema definitions."""
        return []

    @property
    def permissions(self) -> list[str]:
        """Module specific permissions."""
        return []

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        """Default role-to-permission mapping for this module."""
        return {}

