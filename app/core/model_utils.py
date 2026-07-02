"""Utilitaires partagés pour les modèles SQLModel (sans dépendance circulaire)."""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> datetime:
    """Retourne l'heure courante UTC avec timezone (remplace datetime.utcnow déprécié)."""
    return datetime.now(timezone.utc)
