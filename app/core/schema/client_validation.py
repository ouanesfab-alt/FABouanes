from __future__ import annotations

# Re-export client validation schema from app.modules.clients.schemas
from app.modules.clients.schemas import ClientValidationSchema  # noqa: F401

__all__ = ["ClientValidationSchema"]
