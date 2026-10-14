from __future__ import annotations

# Re-export supplier schemas from app.modules.purchases.schemas
from app.modules.purchases.schemas import SupplierValidationSchema  # noqa: F401

__all__ = ["SupplierValidationSchema"]
