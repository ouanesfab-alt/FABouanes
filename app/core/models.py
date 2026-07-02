"""
Hub de re-export des modèles SQLModel.

Les modèles sont définis dans app/core/models_pkg/ (un fichier par domaine métier).
Ce fichier les re-exporte pour la compatibilité descendante :
    from app.core.models import User, Client, Sale  # ← continue de fonctionner
"""
from __future__ import annotations

from app.core.model_utils import _now  # noqa: F401 — re-export pour compatibilité


# ── Re-exports depuis models_pkg ───────────────────────────────────────────────

from app.core.models_pkg.users import User, UserBadge  # noqa: E402, F401
from app.core.models_pkg.clients import Client, ImportedClientHistory, ClientHistory, ClientKey  # noqa: E402, F401
from app.core.models_pkg.catalog import RawMaterial, FinishedProduct, StockMovement, StockAlert  # noqa: E402, F401
from app.core.models_pkg.sales import Sale, RawSale, SaleDocument  # noqa: E402, F401
from app.core.models_pkg.purchases import Supplier, Purchase, PurchaseDocument  # noqa: E402, F401
from app.core.models_pkg.payments import Payment  # noqa: E402, F401
from app.core.models_pkg.expenses import Expense  # noqa: E402, F401
from app.core.models_pkg.production import ProductionBatch, ProductionBatchItem, SavedRecipe, SavedRecipeItem  # noqa: E402, F401


__all__ = [
    "_now",
    # Users
    "User", "UserBadge",
    # Clients
    "Client", "ImportedClientHistory", "ClientHistory", "ClientKey",
    # Catalog
    "RawMaterial", "FinishedProduct", "StockMovement", "StockAlert",
    # Sales
    "Sale", "RawSale", "SaleDocument",
    # Purchases
    "Supplier", "Purchase", "PurchaseDocument",
    # Payments
    "Payment",
    # Expenses
    "Expense",
    # Production
    "ProductionBatch", "ProductionBatchItem", "SavedRecipe", "SavedRecipeItem",
]
