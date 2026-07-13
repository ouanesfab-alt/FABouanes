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
            return str(obj)
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
    force_outbox = os.getenv("FAB_FORCE_OUTBOX") == "1"
    if force_outbox:
        try:
            from app.core.db_helpers import execute_db
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

    # 2. Publish to DB Pub/Sub
    if not is_testing:
        try:
            from app.core.db_helpers import execute_db
            payload = _serialize_event(event, WORKER_ID)
            execute_db(
                "INSERT INTO pubsub_events (channel, payload, sender_worker_id) VALUES (%s, %s, %s)",
                ("fabouanes:events", payload, WORKER_ID)
            )
            # Notifier les autres workers via PostgreSQL LISTEN/NOTIFY
            try:
                execute_db("NOTIFY fabouanes_events")
            except Exception:
                pass  # NOTIFY est un best-effort
        except Exception as e:
            logger.debug("Failed to publish domain event to DB pubsub: %s", e)


# ── Listeners par défaut (remplacent les appels manuels copié-collés) ──


def _auto_audit(event: DomainEvent) -> None:
    """Enregistre automatiquement un événement d'audit."""
    if event.action == "invalidate":
        return
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
    if event.action == "invalidate":
        return
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
            from app.modules.reports.repository import refresh_client_balances_view
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                coro = refresh_client_balances_view()
                loop.create_task(coro)
            else:
                refresh_client_balances_view()
        except Exception:
            logger.debug("Could not refresh client balances view after %s.%s", event.action, event.entity_type)


def _auto_invalidate_cache(event: DomainEvent) -> None:
    if event.action == "invalidate" and event.entity_type == "cache":
        domains = event.extra.get("domains") or []
        if domains:
            try:
                from app.core.perf_cache import _BACKEND
                _BACKEND.invalidate_domains(*domains)
            except Exception as e:
                logger.debug("Failed to handle remote cache invalidation: %s", e)


def _auto_invalidate_client_cache(event: DomainEvent) -> None:
    if event.action == "invalidate" and event.entity_type == "client_cache":
        client_id = event.extra.get("client_id")
        if client_id is not None:
            try:
                from app.core.perf_cache import _BACKEND
                keys_to_delete = [
                    ("client_detail", client_id),
                    ("client_history", client_id),
                    ("client_account", client_id),
                    ("client_detail_context", client_id),
                    ("client_history_context", client_id),
                ]
                with _BACKEND._lock:
                    for key in keys_to_delete:
                        _BACKEND._cache.pop(key, None)
            except Exception as e:
                logger.debug("Failed to handle remote client cache invalidation: %s", e)


def _auto_invalidate_all_cache(event: DomainEvent) -> None:
    if event.action == "invalidate" and event.entity_type == "all_cache":
        try:
            from app.core.perf_cache import _BACKEND
            _BACKEND.clear()
        except Exception as e:
            logger.debug("Failed to clear remote cache: %s", e)


def _auto_check_stock_alert(event: DomainEvent) -> None:
    """Déclenche la vérification des alertes de stock après une modification d'inventaire."""
    if event.action == "invalidate":
        return
    if event.entity_type in ("sale", "purchase", "production_batch", "raw_material", "finished_product"):
        import asyncio
        from app.services.alert_service import check_stock_alerts
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            loop.create_task(check_stock_alerts())
        else:
            try:
                from app.core.helpers import async_compat
                async_compat(check_stock_alerts)()
            except Exception:
                pass


# ── Enregistrement des listeners par défaut au chargement du module ──
on("invalidate.cache", _auto_invalidate_cache)
on("invalidate.client_cache", _auto_invalidate_client_cache)
on("invalidate.all_cache", _auto_invalidate_all_cache)
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

on("create.*", _auto_check_stock_alert)
on("update.*", _auto_check_stock_alert)
on("delete.*", _auto_check_stock_alert)



# Choix importants :
# 1. Utilisation de BackgroundScheduler pour exécuter des tâches récurrentes de façon asynchrone sans bloquer l'application.
# 2. Enregistrement de la tâche daily_overdue_alerts à 8h chaque jour avec replace_existing=True pour éviter les doublons au redémarrage.

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
except ImportError:
    scheduler = None


_db_listener_thread = None
_db_listener_running = False
_last_seen_pubsub_id = 0


def _db_event_listener_loop():
    global _db_listener_running, _last_seen_pubsub_id
    import time
    import select
    from app.core.db_helpers import execute_db, query_db

    # Initialize last seen ID to current max
    try:
        max_row = query_db("SELECT MAX(id) as max_id FROM pubsub_events", one=True)
        if max_row and max_row.get("max_id"):
            _last_seen_pubsub_id = int(max_row["max_id"])
    except Exception:
        pass

    # Try to set up a dedicated LISTEN connection
    listen_conn = None
    listen_fileno = None
    try:
        from app.core.config import DATABASE_URL
        from app.core.db_helpers import pool_manager
        listen_conn = pool_manager.connect_database(DATABASE_URL)
        listen_conn.execute("LISTEN fabouanes_events")
        listen_conn.commit()
        # pg8000 CompatConnection wraps a pg8000 connection; get the raw socket fd
        raw = getattr(listen_conn, '_conn', listen_conn)
        sock = getattr(raw, '_sock', None) or getattr(raw, 'sock', None)
        if sock:
            listen_fileno = sock.fileno()
            logger.info("LISTEN/NOTIFY active on fabouanes_events (fd=%d)", listen_fileno)
        else:
            logger.info("LISTEN/NOTIFY setup: no socket found, falling back to polling")
    except Exception as e:
        logger.info("LISTEN/NOTIFY setup failed (%s), falling back to polling", e)
        listen_conn = None
        listen_fileno = None

    while _db_listener_running:
        try:
            # Wait for notification (or timeout after 5s as fallback)
            if listen_fileno is not None:
                try:
                    readable, _, _ = select.select([listen_fileno], [], [], 5.0)
                    if readable:
                        # Drain notifications from pg8000
                        try:
                            listen_conn.commit()  # pg8000 reads notifications on commit/execute
                        except Exception:
                            pass
                except (OSError, ValueError):
                    # Socket closed, fall back to plain sleep
                    listen_fileno = None
                    time.sleep(5.0)
            else:
                time.sleep(5.0)

            # Poll for new events from other workers
            rows = query_db(
                """
                SELECT id, channel, payload
                FROM pubsub_events
                WHERE sender_worker_id != %s AND id > %s
                ORDER BY id ASC
                """,
                (WORKER_ID, _last_seen_pubsub_id),
            )
            for row in rows or []:
                _last_seen_pubsub_id = max(_last_seen_pubsub_id, int(row["id"]))
                if row["channel"] == "fabouanes:ws_broadcast":
                    try:
                        from app.core.websockets import manager
                        data = json.loads(row["payload"])
                        msg_type = data.get("type")
                        msg = data.get("message")
                        if msg_type == "global":
                            manager._local_broadcast_global(msg)
                        elif msg_type == "user":
                            user_id = data.get("user_id")
                            if user_id is not None:
                                manager._local_broadcast_user(int(user_id), msg)
                    except Exception as e:
                        logger.warning("Failed to process remote websocket broadcast: %s", e)
                else:
                    res = _deserialize_event(row["payload"])
                    if res:
                        event, sender_id = res
                        _trigger_local_handlers(event, skip_default=True)

            # Prune events older than 10 minutes
            execute_db(
                "DELETE FROM pubsub_events WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '10 minutes'"
            )
        except Exception as e:
            logger.debug("Failed to poll/prune pubsub_events: %s", e)
            time.sleep(5.0)  # Rate-limit en cas d'erreur

    # Cleanup LISTEN connection
    if listen_conn:
        try:
            listen_conn.close()
        except Exception:
            pass



def startup():
    """Démarre le planificateur de tâches en arrière-plan et le listener de base de données Pub/Sub."""
    global _db_listener_thread, _db_listener_running
    import threading

    # Start DB Pub/Sub listener
    if not _db_listener_running:
        # Nettoyer les anciens événements au démarrage pour garder la table légère
        try:
            from app.core.db_helpers import execute_db
            execute_db("DELETE FROM pubsub_events WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '10 minutes'")
        except Exception:
            pass
        _db_listener_running = True
        _db_listener_thread = threading.Thread(target=_db_event_listener_loop, daemon=True)
        _db_listener_thread.start()
        logger.info("DB Pub/Sub Event Bus listener started (worker_id=%s, mode=LISTEN/NOTIFY+fallback)", WORKER_ID)

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
    """Arrête le planificateur et le listener DB Pub/Sub."""
    global _db_listener_running, _db_listener_thread
    if scheduler and scheduler.running:
        try:
            scheduler.shutdown()
            logger.info("Scheduler APScheduler arrêté.")
        except Exception as e:
            logger.error("Erreur lors de l'arrêt du scheduler : %s", e)

    if _db_listener_running:
        _db_listener_running = False
        logger.info("DB Pub/Sub Event Bus listener arrêté.")

