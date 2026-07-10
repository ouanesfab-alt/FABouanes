"""Utilitaires partagés pour les modèles SQLModel (sans dépendance circulaire)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

def _now() -> datetime:
    """Retourne l'heure courante UTC sans timezone (naïve) pour compatibilité avec les colonnes TIMESTAMP."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def to_gmt1(dt: Any) -> Any:
    """Convertit un datetime (naïf supposé UTC ou conscient) vers le fuseau GMT+1 (Algérie)."""
    if not isinstance(dt, datetime):
        return dt
    tz_gmt1 = timezone(timedelta(hours=1))
    if dt.tzinfo is not None:
        return dt.astimezone(tz_gmt1)
    else:
        return dt.replace(tzinfo=timezone.utc).astimezone(tz_gmt1)
