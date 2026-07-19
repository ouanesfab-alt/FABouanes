from __future__ import annotations

import os
import json
import asyncio
from typing import Any, Callable

import structlog

from app.core.websockets import manager

logger = structlog.get_logger("fabouanes.worker")


async def update_task_progress(job_id: str, percent: int, message: str) -> None:
    """Updates job progress and broadcasts it over WebSockets."""
    logger.info("Task progress update", job_id=job_id, percent=percent, message=message)
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

    await asyncio.to_thread(generate_invoice_pdf, payload, username)

    await update_task_progress(job_id, 90, "Finalisation de l'écriture du flux PDF...")
    await asyncio.sleep(0.2)
    await update_task_progress(job_id, 100, "PDF généré avec succès.")
    return "pdf_generated"


async def import_excel_task(ctx: dict[str, Any], file_path: str, client_id: int | None, force_reimport: bool = True) -> dict[str, Any]:
    """Imports client excel data in the background."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 10, "Lecture du fichier Excel...")
    await asyncio.sleep(0.5)

    from app.core.async_db import get_async_sessionmaker
    from app.modules.clients.service import ClientService
    await update_task_progress(job_id, 50, "Insertion et rapprochement en base de données...")

    async with get_async_sessionmaker()() as session:
        service = ClientService(session)
        result = await service.import_client_history_from_excel(file_path, client_id, force_reimport)

    await update_task_progress(job_id, 100, f"Import terminé. {result.get('nb_lignes', 0)} lignes insérées.")

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

    await asyncio.to_thread(capture_local_backup_snapshot, reason)

    await update_task_progress(job_id, 100, "Sauvegarde de la base de données terminée.")
    return "backup_completed"


async def dispatch_outbox_events_task(ctx: dict[str, Any]) -> int:
    """
    Polls the outbox_events table for unprocessed events, publishes them to DB Pub/Sub,
    runs the default local handlers, and marks them as processed.
    """
    from app.core.db_helpers import db_transaction

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

            from app.core.events import _deserialize_event, _trigger_local_handlers

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

                    # 1. Run local default handlers
                    try:
                        _trigger_local_handlers(event, skip_default=False)
                    except Exception as e:
                        success = False
                        error_msg = str(e)
                        logger.error("Failed to run local handlers for outbox event", event_id=event_id, error=error_msg)

                    # 2. Publish to DB Pub/Sub for other worker nodes
                    if success:
                        try:
                            conn.execute(
                                "INSERT INTO pubsub_events (channel, payload, sender_worker_id) VALUES (%s, %s, %s)",
                                ("fabouanes:events", payload_str, "outbox_dispatcher")
                            )
                        except Exception as e:
                            logger.warning("Failed to publish outbox event to DB Pub/Sub", event_id=event_id, error=str(e))
                else:
                    success = False
                    error_msg = "Deserialization failed"
                    logger.error("Failed to deserialize event payload", event_id=event_id)

                if success:
                    conn.execute(
                        "UPDATE outbox_events SET processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (event_id,)
                    )
                    events_processed += 1
                else:
                    new_retry_cnt = retry_cnt + 1
                    if new_retry_cnt >= 5:
                        conn.execute(
                            "INSERT INTO dead_letter_events (event_type, payload, reason) VALUES (%s, %s, %s)",
                            (event_type, payload_str, error_msg)
                        )
                        conn.execute(
                            "DELETE FROM outbox_events WHERE id = %s",
                            (event_id,)
                        )
                    else:
                        conn.execute(
                            "UPDATE outbox_events SET retry_count = %s, last_error = %s WHERE id = %s",
                            (new_retry_cnt, error_msg, event_id)
                        )

            conn.commit()
    except Exception as exc:
        logger.error("Error in dispatch_outbox_events_task", error=str(exc))

    return events_processed


async def replay_dead_letter_events_task(ctx: dict[str, Any]) -> int:
    """Replays all events from dead_letter_events table."""
    from app.core.db_helpers import db_transaction

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

                conn.execute(
                    "INSERT INTO outbox_events (event_type, payload, retry_count, last_error) VALUES (%s, %s, 0, NULL)",
                    (event_type, payload)
                )
                conn.execute(
                    "DELETE FROM dead_letter_events WHERE id = %s",
                    (dlq_id,)
                )
                events_replayed += 1

            conn.commit()
    except Exception as exc:
        logger.error("Error in replay_dead_letter_events_task", error=str(exc))

    return events_replayed


TASK_MAPPING: dict[str, Callable[..., Any]] = {
    "generate_invoice_pdf_task": generate_invoice_pdf_task,
    "import_excel_task": import_excel_task,
    "run_database_backup_task": run_database_backup_task,
    "dispatch_outbox_events_task": dispatch_outbox_events_task,
    "replay_dead_letter_events_task": replay_dead_letter_events_task,
}


async def enqueue_background_task(task_name: str, *args: Any, **kwargs: Any) -> str:
    """Inserts a task into the database background_jobs table to be executed by a worker."""
    if task_name not in TASK_MAPPING:
        logger.error("Requested background task name not found in mapping", task=task_name)
        return "invalid-task"

    from app.core.db_helpers import execute_db, query_db
    payload = json.dumps({"args": args, "kwargs": kwargs})
    
    rows = query_db(
        """
        INSERT INTO background_jobs (task_name, payload, status)
        VALUES (%s, %s, 'pending')
        RETURNING id
        """,
        (task_name, payload),
        one=True
    )
    job_id = str(rows["id"]) if rows else f"job-{os.urandom(4).hex()}"
    logger.info("Enqueued background task to database", task=task_name, job_id=job_id)
    
    try:
        execute_db("NOTIFY background_jobs_channel")
    except Exception:
        pass
        
    return job_id


import threading
import time
import select

_worker_thread = None
_worker_running = False


async def execute_job(job_id: int, task_name: str, payload_str: str) -> None:
    func = TASK_MAPPING.get(task_name)
    if not func:
        logger.error("Task not found in mapping", task=task_name, job_id=job_id)
        from app.core.db_helpers import execute_db
        execute_db(
            "UPDATE background_jobs SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s",
            ("Task not found in mapping", job_id)
        )
        return

    try:
        payload = json.loads(payload_str)
    except Exception:
        payload = {}

    args = payload.get("args") or []
    kwargs = payload.get("kwargs") or {}
    ctx = {"job_id": str(job_id)}

    logger.info("Executing background job", job_id=job_id, task=task_name)
    from app.core.db_helpers import execute_db
    try:
        import inspect
        if inspect.iscoroutinefunction(func):
            await func(ctx, *args, **kwargs)
        else:
            func(ctx, *args, **kwargs)

        execute_db(
            "UPDATE background_jobs SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = %s",
            (job_id,)
        )
        logger.info("Successfully completed background job", job_id=job_id, task=task_name)
    except Exception as exc:
        error_msg = str(exc)
        logger.exception("Failed executing background job", job_id=job_id, task=task_name)
        execute_db(
            "UPDATE background_jobs SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP WHERE id = %s",
            (error_msg, job_id)
        )


def _worker_poll_loop():
    global _worker_running
    from app.core.db_helpers import db_transaction
    from app.core.config import DATABASE_URL
    from app.core.db_helpers import pool_manager
    from app.core.events import WORKER_ID

    listen_conn = None
    listen_fileno = None
    try:
        listen_conn = pool_manager.connect_database(DATABASE_URL)
        listen_conn.execute("LISTEN background_jobs_channel")
        listen_conn.commit()
        raw = getattr(listen_conn, '_conn', listen_conn)
        sock = getattr(raw, '_sock', None) or getattr(raw, 'sock', None)
        if sock:
            listen_fileno = sock.fileno()
            logger.info("LISTEN active on background_jobs_channel (fd=%d)", listen_fileno)
    except Exception as e:
        logger.info("LISTEN setup for jobs failed: %s", e)
        listen_conn = None

    while _worker_running:
        try:
            job = None
            try:
                with db_transaction() as conn:
                    cur = conn.execute(
                        """
                        UPDATE background_jobs 
                        SET status = 'running', locked_by = %s, started_at = CURRENT_TIMESTAMP
                        WHERE id = (
                            SELECT id FROM background_jobs 
                            WHERE status = 'pending' AND run_at <= CURRENT_TIMESTAMP
                            ORDER BY priority DESC, created_at ASC
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                        )
                        RETURNING id, task_name, payload;
                        """,
                        (WORKER_ID,)
                    )
                    job = cur.fetchone()
                    conn.commit()
            except Exception as e:
                logger.error("DB error polling jobs: %s", e)
                job = None

            if job:
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(execute_job(job["id"], job["task_name"], job["payload"]))
                    loop.close()
                except Exception as ex:
                    logger.error("Worker runner error: %s", ex)
                continue

            if listen_fileno is not None:
                try:
                    readable, _, _ = select.select([listen_fileno], [], [], 5.0)
                    if readable:
                        try:
                            listen_conn.commit()
                        except Exception:
                            pass
                except (OSError, ValueError):
                    listen_fileno = None
                    time.sleep(5.0)
            else:
                time.sleep(5.0)
        except Exception as exc:
            logger.error("Error in background worker loop: %s", exc)
            time.sleep(5.0)


def start_worker():
    global _worker_thread, _worker_running
    if not _worker_running:
        _worker_running = True
        _worker_thread = threading.Thread(target=_worker_poll_loop, daemon=True)
        _worker_thread.start()
        logger.info("Background jobs worker started successfully")


def stop_worker():
    global _worker_running
    _worker_running = False
    logger.info("Background jobs worker stop requested")
