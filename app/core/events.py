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
import os
import uuid
import json
import decimal
import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("fabouanes.events")

WORKER_ID = uuid.uuid4().hex
_redis_client = None


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


class EventJSONEncoder(json.JSONEncoder):  # pragma: no cover
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def _serialize_event(event: DomainEvent, sender_id: str) -> str:  # pragma: no cover
    data = {
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "label": event.label,
        "before": event.before,
        "after": event.after,
        "source": event.source,
        "extra": event.extra,
        "sender_id": sender_id,
    }
    return json.dumps(data, cls=EventJSONEncoder)


def _deserialize_event(json_str: str) -> tuple[DomainEvent, str] | None:  # pragma: no cover
    try:
        data = json.loads(json_str)
        event = DomainEvent(
            action=data["action"],
            entity_type=data["entity_type"],
            entity_id=data.get("entity_id"),
            label=data.get("label", ""),
            before=data.get("before"),
            after=data.get("after"),
            source=data.get("source", "web"),
            extra=data.get("extra", {}),
        )
        return event, data.get("sender_id", "")
    except Exception as e:
        logger.warning("Failed to deserialize domain event: %s", e)
        return None


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


def _trigger_local_handlers(event: DomainEvent, skip_default: bool = False) -> None:
    patterns = [
        "*",
        f"{event.action}.*",
        f"*.{event.entity_type}",
        f"{event.action}.{event.entity_type}",
    ]
    # Check handler name to avoid duplicate DB operations when distributing events
    default_names = {
        "_auto_audit",
        "_auto_activity",
        "_auto_backup",
        "_auto_websocket",
        "_auto_refresh_balances",
    }
    for pattern in patterns:
        for handler in _listeners.get(pattern, []):
            if skip_default and handler.__name__ in default_names:
                continue
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


def emit(event: DomainEvent) -> None:
    """Publie un événement à tous les listeners concernés (via Outbox si configuré, sinon inline)."""
    is_testing = bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("FAB_TESTING") == "1"
        or os.getenv("FASTAPI_ENV") == "test"
    )
    redis_url = os.environ.get("REDIS_URL", "").strip()
    force_outbox = os.getenv("FAB_FORCE_OUTBOX") == "1"
    if (redis_url and not is_testing) or force_outbox:
        try:
            from app.core.db_access import execute_db
            payload = _serialize_event(event, WORKER_ID)
            execute_db(
                "INSERT INTO outbox_events (event_type, payload) VALUES (%s, %s)",
                (f"{event.action}.{event.entity_type}", payload)
            )
            logger.debug("Event written to outbox table: %s.%s", event.action, event.entity_type)
            return
        except Exception as e:
            logger.error("Failed to write event to outbox table, falling back inline: %s", e)

    # Fallback to legacy inline behavior (run immediately in request thread)
    # 1. Run local handlers immediately
    _trigger_local_handlers(event)

    # 2. Publish to Redis if configured
    if _redis_client:  # pragma: no cover
        try:
            payload = _serialize_event(event, WORKER_ID)
            _redis_client.publish("fabouanes:events", payload)
        except Exception as e:
            logger.warning("Failed to publish domain event to Redis: %s", e)


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


def _auto_websocket(event: DomainEvent) -> None:
    """Diffuse un message WebSocket lors d'une modification d'opération."""
    # Seuls certains types d'entités doivent déclencher un rafraîchissement
    if event.entity_type in ("sale", "purchase", "payment", "sale_document", "purchase_document"):
        from app.core.websockets import manager
        manager.broadcast_sync("refresh_operations")


def _auto_refresh_balances(event: DomainEvent) -> None:
    """Refresh the mv_client_balances materialized view after financial mutations."""
    if event.entity_type in ("sale", "payment", "client", "sale_document"):
        try:
            from app.repositories.dashboard_repository import refresh_client_balances_view
            refresh_client_balances_view()
        except Exception:
            logger.debug("Could not refresh client balances view after %s.%s", event.action, event.entity_type)


# ── Enregistrement des listeners par défaut au chargement du module ──
on("*", _auto_audit)
on("*", _auto_activity)
on("create.*", _auto_backup)
on("update.*", _auto_backup)
on("delete.*", _auto_backup)

on("create.*", _auto_websocket)
on("update.*", _auto_websocket)
on("delete.*", _auto_websocket)

on("create.*", _auto_refresh_balances)
on("update.*", _auto_refresh_balances)
on("delete.*", _auto_refresh_balances)


# Choix importants :
# 1. Utilisation de BackgroundScheduler pour exécuter des tâches récurrentes de façon asynchrone sans bloquer l'application.
# 2. Enregistrement de la tâche daily_overdue_alerts à 8h chaque jour avec replace_existing=True pour éviter les doublons au redémarrage.

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
except ImportError:
    scheduler = None


_redis_thread = None


def _redis_event_handler(message):  # pragma: no cover
    try:
        if message["type"] != "message":
            return
        data_str = message["data"]
        if isinstance(data_str, bytes):
            data_str = data_str.decode("utf-8")
        res = _deserialize_event(data_str)
        if not res:
            return
        event, sender_id = res
        if sender_id == WORKER_ID:
            return
        _trigger_local_handlers(event, skip_default=True)
    except Exception as e:
        logger.exception("Error in Redis event handler")


def _start_redis_listener():  # pragma: no cover
    global _redis_thread
    if not _redis_client:
        return
    try:
        pubsub = _redis_client.pubsub()
        pubsub.subscribe(**{"fabouanes:events": _redis_event_handler})
        _redis_thread = pubsub.run_in_thread(sleep_time=0.1, daemon=True)
        logger.info("Redis Event Bus listener started (worker_id=%s)", WORKER_ID)
    except Exception as e:
        logger.error("Failed to start Redis Event Bus listener: %s", e)


def startup():
    """Démarre le planificateur de tâches en arrière-plan et le listener Redis."""
    # Démarrage de l'écouteur Redis
    _start_redis_listener()

    if scheduler:
        try:
            if not scheduler.running:
                scheduler.start()
            from app.services.alert_service import broadcast_overdue_alerts
            scheduler.add_job(
                broadcast_overdue_alerts,
                "cron", hour=8, minute=0,  # Chaque jour à 8h
                id="daily_overdue_alerts",
                replace_existing=True,
            )
            logger.info("Scheduler APScheduler démarré et tâche d'alertes enregistrée.")
        except Exception as e:
            logger.error("Erreur lors du démarrage du scheduler : %s", e)


def shutdown():
    """Arrête le planificateur et le listener Redis."""
    global _redis_thread
    if scheduler and scheduler.running:
        try:
            scheduler.shutdown()
            logger.info("Scheduler APScheduler arrêté.")
        except Exception as e:
            logger.error("Erreur lors de l'arrêt du scheduler : %s", e)
    if _redis_thread:  # pragma: no cover
        try:
            _redis_thread.stop()
            logger.info("Redis Event Bus listener arrêté.")
        except Exception:
            pass

