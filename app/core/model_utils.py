"""Utilitaires partagés pour les modèles SQLModel (sans dépendance circulaire)."""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> datetime:
    """Retourne l'heure courante UTC sans timezone (naïve) pour compatibilité avec les colonnes TIMESTAMP."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
