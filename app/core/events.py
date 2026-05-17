"""
Event Bus interne léger — découple les services des effets secondaires.

Usage:
    from app.core.events import emit, DomainEvent

    # Dans un service:
    emit(DomainEvent("create", "raw_material", item_id, name, after=created))

    # Enregistrer un listener custom:
    from app.core.events import on
    on("create.raw_material", my_handler)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("fabouanes.events")


@dataclass
class DomainEvent:
    """Événement métier standardisé."""

    action: str  # "create", "update", "delete"
    entity_type: str  # "raw_material", "sale", "client", ...
    entity_id: int | None = None
    label: str = ""
    before: Any = None
    after: Any = None
    source: str = "web"
    extra: dict = field(default_factory=dict)


# ── Registre global des listeners ──
_listeners: dict[str, list[Callable]] = defaultdict(list)


def on(event_pattern: str, handler: Callable) -> None:
    """Enregistre un listener.

    Patterns supportés:
        '*'                → tous les événements
        'create.*'         → toutes les créations
        '*.client'         → tout ce qui touche aux clients
        'create.client'    → création de client uniquement
    """
    _listeners[event_pattern].append(handler)


def off(event_pattern: str, handler: Callable) -> None:
    """Supprime un listener."""
    handlers = _listeners.get(event_pattern, [])
    if handler in handlers:
        handlers.remove(handler)


def emit(event: DomainEvent) -> None:
    """Publie un événement à tous les listeners concernés."""
    patterns = [
        "*",
        f"{event.action}.*",
        f"*.{event.entity_type}",
        f"{event.action}.{event.entity_type}",
    ]
    for pattern in patterns:
        for handler in _listeners.get(pattern, []):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler error: %s on pattern '%s' for event %s.%s",
                    handler.__name__,
                    pattern,
                    event.action,
                    event.entity_type,
                )


# ── Listeners par défaut (remplacent les appels manuels copié-collés) ──


def _auto_audit(event: DomainEvent) -> None:
    """Enregistre automatiquement un événement d'audit."""
    from app.core.audit import audit_event

    audit_event(
        f"{event.action}_{event.entity_type}",
        event.entity_type,
        event.entity_id,
        source=event.source,
        before=event.before,
        after=event.after,
    )


def _auto_activity(event: DomainEvent) -> None:
    """Log l'activité utilisateur automatiquement."""
    from app.core.activity import log_activity

    log_activity(
        f"{event.action}_{event.entity_type}",
        event.entity_type,
        event.entity_id,
        event.label,
    )


def _auto_backup(event: DomainEvent) -> None:
    """Déclenche un backup après les mutations (create/update/delete)."""
    from app.core.storage import backup_database

    backup_database(f"{event.action}_{event.entity_type}")


# ── Enregistrement des listeners par défaut au chargement du module ──
on("*", _auto_audit)
on("*", _auto_activity)
on("create.*", _auto_backup)
on("update.*", _auto_backup)
on("delete.*", _auto_backup)
