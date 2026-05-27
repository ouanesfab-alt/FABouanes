from __future__ import annotations

import os
import json
import logging
import asyncio
from typing import Any, Callable

import structlog
from arq.connections import RedisSettings, ArqRedis
from arq import create_pool, cron

from app.core.websockets import manager

logger = structlog.get_logger("fabouanes.worker")


async def update_task_progress(job_id: str, percent: int, message: str) -> None:
    """Updates job progress in Redis and broadcasts it over WebSockets."""
    logger.info("Task progress update", job_id=job_id, percent=percent, message=message)
    # Broadcast through our WebSocket connection manager
    try:
        payload = json.dumps({
            "type": "task_progress",
            "task_id": job_id,
            "percent": percent,
            "message": message,
        })
        manager.broadcast_sync(payload)
    except Exception as exc:
        logger.warning("Failed to broadcast task progress over WebSockets", error=str(exc))


# --- Task Definitions ---

async def generate_invoice_pdf_task(ctx: dict[str, Any], payload: dict[str, Any], username: str) -> str:
    """Generates an invoice PDF in the background."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 10, "Initialisation de la génération PDF...")
    await asyncio.sleep(0.5)

    from app.services.print_service import generate_invoice_pdf
    await update_task_progress(job_id, 40, "Génération des layouts de facturation...")
    
    # Run CPU intensive PDF generation in threadpool to avoid blocking event loop
    pdf_buf = await asyncio.to_thread(generate_invoice_pdf, payload, username)
    
    await update_task_progress(job_id, 90, "Finalisation de l'écriture du flux PDF...")
    await asyncio.sleep(0.2)
    await update_task_progress(job_id, 100, "PDF généré avec succès.")
    return "pdf_generated"


async def import_excel_task(ctx: dict[str, Any], file_path: str, client_id: int | None, force_reimport: bool = True) -> dict[str, Any]:
    """Imports client excel data in the background."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 10, "Lecture du fichier Excel...")
    await asyncio.sleep(0.5)

    from app.services.client_import_service import import_client_history_from_excel
    await update_task_progress(job_id, 50, "Insertion et rapprochement en base de données...")
    
    # Run blocking file import in threadpool
    result = await asyncio.to_thread(import_client_history_from_excel, file_path, client_id, force_reimport)
    
    await update_task_progress(job_id, 100, f"Import terminé. {result.get('nb_lignes', 0)} lignes insérées.")
    
    # Clean up the temp file after background processing is finished
    try:
         if os.path.exists(file_path):
             os.unlink(file_path)
    except Exception as exc:
         logger.warning("Failed to clean up temporary Excel file in worker", path=file_path, error=str(exc))
         
    return result


async def run_database_backup_task(ctx: dict[str, Any], reason: str) -> str:
    """Runs a database backup in the background."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 20, "Vérification de l'intégrité de la base...")
    await asyncio.sleep(0.5)

    from app.core.storage import capture_local_backup_snapshot
    await update_task_progress(job_id, 60, "Écriture du dump PostgreSQL...")
    
    # Run blocking shell backup command in threadpool
    await asyncio.to_thread(capture_local_backup_snapshot, reason)
    
    await update_task_progress(job_id, 100, "Sauvegarde de la base de données terminée.")
    return "backup_completed"


async def dispatch_outbox_events_task(ctx: dict[str, Any]) -> int:
    """
    Polls the outbox_events table for unprocessed events, publishes them to Redis Pub/Sub,
    runs the default local handlers, and marks them as processed.
    Redirects failing events to dead_letter_events after 5 retries.
    """
    from app.core.db_access import db_transaction
    
    events_processed = 0
    try:
        with db_transaction() as conn:
            cur = conn.execute(
                "SELECT id, event_type, payload, retry_count FROM outbox_events WHERE processed_at IS NULL ORDER BY id ASC LIMIT 100 FOR UPDATE SKIP LOCKED"
            )
            rows = cur.fetchall()
            cur.close()
            
            if not rows:
                return 0
                
            from app.core.events import _deserialize_event, _trigger_local_handlers, _redis_client
            
            for row in rows:
                event_id = row["id"]
                payload_str = row["payload"]
                retry_cnt = row["retry_count"] or 0
                event_type = row["event_type"]
                
                res = _deserialize_event(payload_str)
                success = True
                error_msg = ""
                
                if res:
                    event, sender_id = res
                    
                    # 1. Run local default handlers in this worker process
                    try:
                        _trigger_local_handlers(event, skip_default=False)
                    except Exception as e:
                        success = False
                        error_msg = str(e)
                        logger.error("Failed to run local handlers for outbox event", event_id=event_id, error=error_msg)
                    
                    # 2. Publish to Redis Pub/Sub for other worker nodes to receive and update state/websockets
                    if success and _redis_client:
                        try:
                            _redis_client.publish("fabouanes:events", payload_str)
                        except Exception as e:
                            logger.warning("Failed to publish outbox event to Redis Pub/Sub", event_id=event_id, error=str(e))
                else:
                    success = False
                    error_msg = "Deserialization failed"
                    logger.error("Failed to deserialize event payload", event_id=event_id)
                            
                if success:
                    # Mark as processed
                    conn.execute(
                        "UPDATE outbox_events SET processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (event_id,)
                    )
                    events_processed += 1
                else:
                    new_retry_cnt = retry_cnt + 1
                    if new_retry_cnt >= 5:
                        # Move to dead letter queue
                        conn.execute(
                            "INSERT INTO dead_letter_events (event_type, payload, reason) VALUES (%s, %s, %s)",
                            (event_type, payload_str, error_msg)
                        )
                        # Remove from outbox
                        conn.execute(
                            "DELETE FROM outbox_events WHERE id = %s",
                            (event_id,)
                        )
                    else:
                        # Update retry count and last error
                        conn.execute(
                            "UPDATE outbox_events SET retry_count = %s, last_error = %s WHERE id = %s",
                            (new_retry_cnt, error_msg, event_id)
                        )
                
            conn.commit()
    except Exception as exc:
        logger.error("Error in dispatch_outbox_events_task", error=str(exc))
        
    return events_processed


async def replay_dead_letter_events_task(ctx: dict[str, Any]) -> int:
    """
    Replays all events from dead_letter_events table by inserting them back
    into outbox_events (with retry_count=0, last_error=NULL) and deleting them from DLQ.
    """
    from app.core.db_access import db_transaction
    
    events_replayed = 0
    try:
        with db_transaction() as conn:
            cur = conn.execute(
                "SELECT id, event_type, payload FROM dead_letter_events ORDER BY id ASC"
            )
            rows = cur.fetchall()
            cur.close()
            
            if not rows:
                return 0
                
            for row in rows:
                dlq_id = row["id"]
                event_type = row["event_type"]
                payload = row["payload"]
                
                # Insert back into outbox_events
                conn.execute(
                    "INSERT INTO outbox_events (event_type, payload, retry_count, last_error) VALUES (%s, %s, 0, NULL)",
                    (event_type, payload)
                )
                
                # Delete from DLQ
                conn.execute(
                    "DELETE FROM dead_letter_events WHERE id = %s",
                    (dlq_id,)
                )
                events_replayed += 1
                
            conn.commit()
    except Exception as exc:
        logger.error("Error in replay_dead_letter_events_task", error=str(exc))
        
    return events_replayed


# --- Client & Fallback Enqueue Helpers ---

TASK_MAPPING: dict[str, Callable[..., Any]] = {
    "generate_invoice_pdf_task": generate_invoice_pdf_task,
    "import_excel_task": import_excel_task,
    "run_database_backup_task": run_database_backup_task,
    "dispatch_outbox_events_task": dispatch_outbox_events_task,
    "replay_dead_letter_events_task": replay_dead_letter_events_task,
}

_arq_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


async def get_arq_pool() -> ArqRedis | None:
    """Returns the ArqRedis pool singleton, initializing if necessary."""
    global _arq_pool
    async with _pool_lock:
        if _arq_pool is not None:
            return _arq_pool
        redis_url = os.environ.get("REDIS_URL", "").strip()
        if not redis_url:
            return None
        try:
            settings = RedisSettings.from_dsn(redis_url)
            _arq_pool = await create_pool(settings)
            return _arq_pool
        except Exception as exc:
            logger.warning("Could not initialize ArqRedis pool, falling back to inline threads", error=str(exc))
            return None


async def enqueue_background_task(task_name: str, *args: Any, **kwargs: Any) -> str:
    """
    Enqueues a task to the background worker pool if available.
    Falls back to inline/threaded execution if Redis is not active.
    """
    pool = await get_arq_pool()
    if pool is not None:
        try:
            job = await pool.enqueue_job(task_name, *args, **kwargs)
            logger.info("Enqueued task to Arq worker pool", task=task_name, job_id=job.job_id)
            return str(job.job_id)
        except Exception as exc:
            logger.warning("Arq enqueuing failed, falling back inline", task=task_name, error=str(exc))

    # Clean fallback execution
    fallback_job_id = f"fallback-{os.urandom(4).hex()}"
    func = TASK_MAPPING.get(task_name)
    if func:
        ctx = {"job_id": fallback_job_id}
        logger.info("Running background task in fallback inline mode", task=task_name, job_id=fallback_job_id)
        # Spin task in background task without blocking the main request thread
        asyncio.create_task(func(ctx, *args, **kwargs))
    else:
        logger.error("Requested background task name not found in mapping", task=task_name)
    return fallback_job_id


# --- Worker Configuration class for Arq CLI CLI Settings ---

class WorkerSettings:
    functions = list(TASK_MAPPING.values())
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    cron_jobs = [
        cron(dispatch_outbox_events_task, second=None, unique=True)
    ]
