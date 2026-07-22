from __future__ import annotations

import os
import json
import asyncio
import threading
import time
import select
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
    await update_task_progress(job_id, 60, "Écriture du dump de la base de données...")

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
                "SELECT id, event_type, payload, retry_count FROM outbox_events WHERE processed_at IS NULL ORDER BY id ASC LIMIT 100"
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


async def rebuild_catalog_embeddings_task(ctx: dict[str, Any], api_key: str = None) -> int:
    """Regenerates embeddings for all catalog items that do not have them yet."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 10, "Démarrage de la génération d'embeddings du catalogue...")

    if not api_key:
        # Use the plugin registry instead of a direct import from app.modules.assistant.
        # The assistant module registers 'get_api_key' at startup via plugin_registry.
        from app.core.plugin_registry import registry
        api_key = registry.call("get_api_key")
    if not api_key:
        logger.error("No Gemini API key available for embedding task")
        await update_task_progress(job_id, 100, "Erreur: Clé API manquante.")
        return 0

    from app.core.db_helpers import query_db, execute_db
    # get_embedding is also resolved via the plugin registry.
    from app.core.plugin_registry import registry as _registry

    raw_mats = query_db("SELECT id, name, unit FROM raw_materials") or []
    fin_prods = query_db("SELECT id, name, default_unit FROM finished_products") or []

    total_items = len(raw_mats) + len(fin_prods)
    if total_items == 0:
        await update_task_progress(job_id, 100, "Catalogue vide, aucune action requise.")
        return 0

    has_vector = False
    try:
        row = query_db("SELECT 1 FROM pg_extension WHERE extname = 'vector'", one=True)
        has_vector = bool(row)
    except Exception:
        pass

    processed = 0
    await update_task_progress(job_id, 20, f"Traitement de {total_items} articles...")

    for item in raw_mats:
        item_id = item["id"]
        existing = query_db("SELECT 1 FROM catalog_embeddings WHERE item_kind = 'raw' AND item_id = %s", (item_id,), one=True)
        if existing:
            continue

        text = f"Matière première: {item['name']}, unité: {item.get('unit') or 'kg'}"
        emb = await _registry.acall("get_embedding", text, api_key)
        if emb:
            emb_val = f"[{','.join(str(x) for x in emb)}]" if has_vector else json.dumps(emb)
            execute_db(
                "INSERT INTO catalog_embeddings (item_kind, item_id, text_content, embedding) VALUES ('raw', %s, %s, %s) ON CONFLICT DO NOTHING",
                (item_id, text, emb_val)
            )
            processed += 1
            await update_task_progress(job_id, int(20 + 80 * (processed / total_items)), f"Génération: {processed}/{total_items} articles...")

    for item in fin_prods:
        item_id = item["id"]
        existing = query_db("SELECT 1 FROM catalog_embeddings WHERE item_kind = 'finished' AND item_id = %s", (item_id,), one=True)
        if existing:
            continue

        text = f"Produit fini: {item['name']}, unité: {item.get('default_unit') or 'kg'}"

        emb = await _registry.acall("get_embedding", text, api_key)
        if emb:
            emb_val = f"[{','.join(str(x) for x in emb)}]" if has_vector else json.dumps(emb)
            execute_db(
                "INSERT INTO catalog_embeddings (item_kind, item_id, text_content, embedding) VALUES ('finished', %s, %s, %s) ON CONFLICT DO NOTHING",
                (item_id, text, emb_val)
            )
            processed += 1
            await update_task_progress(job_id, int(20 + 80 * (processed / total_items)), f"Génération: {processed}/{total_items} articles...")

    # Indexer le manuel utilisateur bilingue pour la recherche vectorielle (RAG Hybride)
    from app.web.manual_pages import SPECIFIC_CHAPTER_DATA
    for key, data in SPECIFIC_CHAPTER_DATA.items():
        try:
            major, minor = map(int, key.split("-"))
            m_id = major * 100 + minor
        except Exception:
            continue
        existing = query_db("SELECT 1 FROM catalog_embeddings WHERE item_kind = 'manual' AND item_id = %s", (m_id,), one=True)
        if existing:
            continue
        text = f"Section Manuel {key}: {data.get('fr_title')} / {data.get('ar_title')}. Usage: {' '.join(data.get('fr_usage', []))} {' '.join(data.get('ar_usage', []))}. Exemple: {data.get('fr_example')} {data.get('ar_example')}"
        emb = await _registry.acall("get_embedding", text, api_key)
        if emb:
            emb_val = f"[{','.join(str(x) for x in emb)}]" if has_vector else json.dumps(emb)
            execute_db(
                "INSERT INTO catalog_embeddings (item_kind, item_id, text_content, embedding) VALUES ('manual', %s, %s, %s) ON CONFLICT DO NOTHING",
                (m_id, text, emb_val)
            )
            processed += 1

    await update_task_progress(job_id, 100, f"Génération terminée. {processed} nouveaux articles indexés sémantiquement.")
    return processed



async def process_offline_staging_task(ctx: dict[str, Any]) -> int:
    """Processes pending staging entries for offline sales and payments."""
    job_id = ctx.get("job_id", "direct-run")
    await update_task_progress(job_id, 10, "Démarrage du traitement de la synchronisation hors-ligne...")

    from app.core.db_helpers import query_db, execute_db
    from app.core.async_db import get_async_sessionmaker
    from app.modules.sales.service import SalesService
    from app.modules.sales.schemas_validation import SaleFormSchema
    from app.services.payment_service import create_payment_from_form
    from app.core.idempotency import check_idempotency, save_idempotency

    pending_sales = query_db("SELECT id, idempotency_key, payload FROM offline_sales_staging WHERE status = 'pending' ORDER BY id ASC") or []
    processed_count = 0

    if pending_sales:
        async_sessionmaker = get_async_sessionmaker()
        async with async_sessionmaker() as session:
            sales_service = SalesService(session)
            for r in pending_sales:
                staging_id = r["id"]
                idempotency_key = r["idempotency_key"]
                payload_str = r["payload"]

                if idempotency_key:
                    cached_res = await check_idempotency(idempotency_key)
                    if cached_res is not None:
                        execute_db(
                            "UPDATE offline_sales_staging SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (staging_id,)
                        )
                        continue

                try:
                    payload = json.loads(payload_str)
                    validated = SaleFormSchema(**payload)
                    await sales_service.create_sale_from_form(validated)
                    await session.commit()

                    if idempotency_key:
                        await save_idempotency(idempotency_key, {"content": {"ok": True}, "status_code": 200})

                    execute_db(
                        "UPDATE offline_sales_staging SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (staging_id,)
                    )
                    processed_count += 1
                except Exception as exc:
                    execute_db(
                        "UPDATE offline_sales_staging SET status = 'failed', error_message = %s, processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (str(exc), staging_id)
                    )

    pending_payments = query_db("SELECT id, idempotency_key, payload FROM offline_payments_staging WHERE status = 'pending' ORDER BY id ASC") or []
    if pending_payments:
        for r in pending_payments:
            staging_id = r["id"]
            idempotency_key = r["idempotency_key"]
            payload_str = r["payload"]

            if idempotency_key:
                cached_res = await check_idempotency(idempotency_key)
                if cached_res is not None:
                    execute_db(
                        "UPDATE offline_payments_staging SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (staging_id,)
                    )
                    continue

            try:
                payload = json.loads(payload_str)
                from app.core.db_helpers import db_transaction
                with db_transaction():
                    await create_payment_from_form(payload)

                if idempotency_key:
                    await save_idempotency(idempotency_key, {"content": {"ok": True}, "status_code": 200})

                execute_db(
                    "UPDATE offline_payments_staging SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (staging_id,)
                )
                processed_count += 1
            except Exception as exc:
                execute_db(
                    "UPDATE offline_payments_staging SET status = 'failed', error_message = %s, processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (str(exc), staging_id)
                )

    await update_task_progress(job_id, 100, f"Synchronisation hors-ligne terminée. {processed_count} opérations synchronisées.")
    return processed_count


TASK_MAPPING: dict[str, Callable[..., Any]] = {
    "generate_invoice_pdf_task": generate_invoice_pdf_task,
    "import_excel_task": import_excel_task,
    "run_database_backup_task": run_database_backup_task,
    "dispatch_outbox_events_task": dispatch_outbox_events_task,
    "replay_dead_letter_events_task": replay_dead_letter_events_task,
    "rebuild_catalog_embeddings_task": rebuild_catalog_embeddings_task,
    "process_offline_staging_task": process_offline_staging_task,
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


_worker_thread = None
_worker_running = False
# Single asyncio event loop reused for all background jobs in the worker thread.
# Created once when the worker starts, closed when it stops.
# This avoids the cost of creating a new event loop per job and prevents
# resource leaks (open DB connections, file descriptors) from orphaned loops.
_worker_loop: asyncio.AbstractEventLoop | None = None


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


def cleanup_background_jobs():
    """Cleans up completed/failed jobs, stale pubsub events, and expired idempotency keys."""
    from app.core.db_helpers import execute_db
    try:
        # 1. Reset timed-out running jobs (>2h) — prevents stuck jobs from blocking the queue
        execute_db(
            """
            UPDATE background_jobs 
            SET status = 'failed', error_message = 'Job timed out or worker crashed'
            WHERE status = 'running' AND started_at < datetime('now', '-2 hours')
            """
        )
        # 2. Purge old completed jobs (>24h)
        execute_db(
            "DELETE FROM background_jobs WHERE status = 'completed' AND completed_at < datetime('now', '-24 hours')"
        )
        # 3. Purge old failed jobs (>7 days)
        execute_db(
            "DELETE FROM background_jobs WHERE status = 'failed' AND completed_at < datetime('now', '-7 days')"
        )
        # 4. P1.5 — Purge old pubsub events (>24h) — prevents unbounded table growth
        try:
            execute_db(
                "DELETE FROM pubsub_events WHERE created_at < datetime('now', '-1 day')"
            )
        except Exception as exc:
            logger.debug("pubsub_events cleanup skipped: %s", exc)

        # 5. P1.5 — Purge expired idempotency keys (>7 days) — prevents unbounded table growth
        try:
            execute_db(
                "DELETE FROM idempotent_requests WHERE created_at < datetime('now', '-7 days')"
            )
        except Exception as exc:
            logger.debug("idempotent_requests cleanup skipped: %s", exc)

        # 6. Purge processed offline staging entries (>30 days)
        try:
            for tbl in ("offline_sales_staging", "offline_payments_staging"):
                execute_db(
                    f"DELETE FROM {tbl} WHERE status != 'pending' AND processed_at < datetime('now', '-30 days')"
                )
        except Exception as exc:
            logger.debug("offline staging cleanup skipped: %s", exc)

        logger.info("Completed stale job recovery and database cleanup (jobs + pubsub + idempotency)")
    except Exception as exc:
        logger.error("Failed to run background jobs cleanup: %s", exc)


def _worker_poll_loop():
    global _worker_running
    from app.core.db_helpers import db_transaction
    from app.core.config import DATABASE_URL
    from app.core.db_helpers import pool_manager
    from app.core.events import WORKER_ID

    listen_conn = None
    listen_fileno = None
    if not DATABASE_URL.startswith("sqlite"):
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

    last_cleanup = 0

    while _worker_running:
        try:
            now_ts = time.time()
            if now_ts - last_cleanup > 3600:
                cleanup_background_jobs()
                last_cleanup = now_ts

            job = None
            try:
                with db_transaction() as conn:
                    row = conn.execute(
                        """
                        SELECT id, task_name, payload FROM background_jobs 
                        WHERE status = 'pending' AND (run_at IS NULL OR run_at <= CURRENT_TIMESTAMP)
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        """
                    ).fetchone()
                    if row:
                        conn.execute(
                            "UPDATE background_jobs SET status = 'running', locked_by = ?, started_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (WORKER_ID, row["id"])
                        )
                        conn.commit()
                        job = row
            except Exception as e:
                err_str = str(e)
                if "42P01" in err_str or "background_jobs" in err_str.lower():
                    try:
                        from app.core.db_helpers import execute_db
                        execute_db("""
                            CREATE TABLE IF NOT EXISTS background_jobs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                task_name VARCHAR(255) NOT NULL,
                                payload TEXT NOT NULL,
                                status VARCHAR(50) DEFAULT 'pending',
                                priority INTEGER DEFAULT 0,
                                run_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                                locked_by VARCHAR(255),
                                started_at TIMESTAMPTZ,
                                completed_at TIMESTAMPTZ,
                                error_message TEXT,
                                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        execute_db("""
                            CREATE INDEX IF NOT EXISTS idx_background_jobs_status_run_at
                            ON background_jobs(status, run_at)
                        """)
                        logger.info("background_jobs table created automatically by worker self-healing")
                    except Exception as create_err:
                        logger.warning("Could not auto-create background_jobs table: %s", create_err)
                else:
                    logger.error("DB error polling jobs: %s", e)
                job = None


            if job:
                try:
                    # Reuse the single event loop dedicated to this worker thread
                    # instead of creating a new one per job (which was wasteful and
                    # could leak resources like DB connections and file descriptors).
                    global _worker_loop
                    if _worker_loop is None or _worker_loop.is_closed():
                        _worker_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(_worker_loop)
                    _worker_loop.run_until_complete(
                        execute_job(job["id"], job["task_name"], job["payload"])
                    )
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
        cleanup_background_jobs()
        _worker_running = True
        _worker_thread = threading.Thread(target=_worker_poll_loop, daemon=True)
        _worker_thread.start()
        logger.info("Background jobs worker started successfully")


def stop_worker():
    global _worker_running, _worker_loop
    _worker_running = False
    # Close the reusable event loop cleanly on shutdown to free all resources.
    if _worker_loop is not None and not _worker_loop.is_closed():
        try:
            _worker_loop.close()
        except Exception:
            pass
        _worker_loop = None
    logger.info("Background jobs worker stop requested")
