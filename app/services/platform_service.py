from __future__ import annotations
from app.core.config import settings

class PlatformService:
    @staticmethod
    def is_desktop() -> bool:
        """Return True if running in Desktop (Electron wrapper) mode."""
        return settings.desktop_mode

    @staticmethod
    def is_server() -> bool:
        """Return True if running in standard server deployment mode."""
        return not settings.desktop_mode

    @staticmethod
    def should_apply_strict_csp() -> bool:
        """Strict CSP nonce-based policy should only be applied in server mode when configured."""
        return settings.strict_csp and not settings.desktop_mode



# Global helper instance
platform = PlatformService()
