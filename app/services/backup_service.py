from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib

from app.core.config import APP_DATA_DIR, DATABASE_URL
from app.core.audit import audit_event
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.db import connect_database
from app.core.helpers import async_compat

logger = logging.getLogger("fabouanes")

SCHEDULER_LOCK_ID = 48216731
BACKGROUND_STATE = {
    "started": False,
    "thread": None,
    "leader_conn": None,
    "last_run_ts": 0,
    "last_backup_ts": 0,
    "shutdown_requested": False,
}

BACKGROUND_LOCK = threading.RLock()
BACKUP_CREATE_IN_WORKER = "__create_on_worker__"


def _shutdown_requested() -> bool:
    with BACKGROUND_LOCK:
        return bool(BACKGROUND_STATE.get("shutdown_requested"))


def _calculate_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _event_backup_interval_seconds() -> int:
    raw = os.getenv("FAB_EVENT_BACKUP_INTERVAL_SECONDS", "600")
    try:
        return max(60, int(raw))
    except Exception:
        return 600


async def _get_setting_db(key: str, default: str, db: AsyncSession) -> str:
    res = await db.execute(text("SELECT value FROM app_settings WHERE key = :key"), {"key": key})
    row = res.first()
    return row.value if row else default


async def _set_setting_db(key: str, value: str, db: AsyncSession) -> None:
    await db.execute(
        text("""
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (:key, :value, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """),
        {"key": key, "value": value}
    )


@async_compat
async def get_backup_settings(db: AsyncSession | None = None) -> dict[str, Any]:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_backup_settings_impl(session)
    return await _get_backup_settings_impl(db)


async def _get_backup_settings_impl(db: AsyncSession) -> dict[str, Any]:
    gdrive = await _get_setting_db("gdrive_backup_dir", "", db)
    snapshot = await _get_setting_db("backup_snapshot_time", "02:00", db)
    local_ret = await _get_setting_db("backup_local_retention", "30", db)
    event_ret = await _get_setting_db("backup_event_retention", "100", db)
    last_nightly = await _get_setting_db("backup_last_nightly_date", "", db)
    pg_dump = await _get_setting_db("pg_dump_path", "", db)
    return {
        "gdrive_backup_dir": gdrive,
        "backup_snapshot_time": snapshot,
        "backup_local_retention": int(local_ret or 30),
        "backup_event_retention": int(event_ret or 100),
        "backup_last_nightly_date": last_nightly,
        "pg_dump_path": pg_dump,
    }


@async_compat
async def save_backup_configuration(payload: dict[str, Any], db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _save_backup_configuration_impl(payload, session)
            await session.commit()
            return
    await _save_backup_configuration_impl(payload, db)


async def _save_backup_configuration_impl(payload: dict[str, Any], db: AsyncSession) -> None:
    fields = {
        "gdrive_backup_dir": str(payload.get("gdrive_backup_dir", "") or "").strip(),
        "backup_snapshot_time": str(payload.get("backup_snapshot_time", "02:00") or "02:00").strip(),
        "backup_local_retention": str(payload.get("backup_local_retention", 30) or 30).strip(),
        "backup_event_retention": str(payload.get("backup_event_retention", 100) or 100).strip(),
        "pg_dump_path": str(payload.get("pg_dump_path", "") or "").strip(),
    }
    for key, value in fields.items():
        await _set_setting_db(key, value, db)


@async_compat
async def enqueue_backup_upload(
    reason: str,
    backup_type: str,
    local_path: str | Path,
    *,
    requested_by_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _enqueue_backup_upload_impl(reason, backup_type, local_path, requested_by_user_id, meta, session)
            await session.commit()
            return res
    return await _enqueue_backup_upload_impl(reason, backup_type, local_path, requested_by_user_id, meta, db)


async def _enqueue_backup_upload_impl(
    reason: str,
    backup_type: str,
    local_path: str | Path,
    requested_by_user_id: int | None,
    meta: dict[str, Any] | None,
    db: AsyncSession,
) -> int:
    res = await db.execute(
        text("""
        INSERT INTO backup_jobs (
            reason,
            backup_type,
            local_path,
            requested_by_user_id,
            status,
            context_json,
            created_at
        ) VALUES (:reason, :backup_type, :local_path, :requested_by_user_id, 'pending', :context_json, CURRENT_TIMESTAMP)
        RETURNING id
        """),
        {
            "reason": reason,
            "backup_type": backup_type,
            "local_path": str(local_path),
            "requested_by_user_id": requested_by_user_id,
            "context_json": "" if meta is None else json.dumps(meta, ensure_ascii=True, sort_keys=True),
        },
    )
    row = res.first()
    return int(row.id) if row else 0


@async_compat
async def enqueue_backup_snapshot(
    reason: str,
    backup_type: str = "manual",
    *,
    requested_by_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> int:
    return await enqueue_backup_upload(
        reason,
        backup_type,
        BACKUP_CREATE_IN_WORKER,
        requested_by_user_id=requested_by_user_id,
        meta={"create_snapshot": True, **(meta or {})},
        db=db,
    )


@async_compat
async def list_backup_jobs(limit: int = 40, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_backup_jobs_impl(limit, session)
    return await _list_backup_jobs_impl(limit, db)


async def _list_backup_jobs_impl(limit: int, db: AsyncSession):
    res = await db.execute(
        text("""
        SELECT bj.*,
               u.username AS requested_by_username
        FROM backup_jobs bj
        LEFT JOIN users u ON u.id = bj.requested_by_user_id
        ORDER BY bj.id DESC
        LIMIT :limit
        """),
        {"limit": int(limit)},
    )
    return [dict(row._mapping) for row in res.all()]


async def _record_backup_run(job_id: int, status: str, *, cloud_file_name: str = "", details: str = "", db: AsyncSession) -> None:
    await db.execute(
        text("""
        INSERT INTO backup_runs (job_id, status, cloud_file_id, cloud_file_name, details_json, started_at, finished_at)
        VALUES (:job_id, :status, '', :cloud_file_name, :details, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "job_id": job_id,
            "status": status,
            "cloud_file_name": cloud_file_name,
            "details": details,
        },
    )


async def _retention_limit_for_type(backup_type: str, db: AsyncSession) -> int:
    settings = await _get_backup_settings_impl(db)
    return settings["backup_local_retention"] if backup_type == "nightly" else settings["backup_event_retention"]


async def _apply_retention_to_directory(directory: Path, backup_type: str, db: AsyncSession) -> None:
    # Gestion des extensions de sauvegarde (.sql.gz.enc, .sql.gz, .sql)
    all_files = []
    for pattern in ("*.sql.gz.enc", "*.sql.gz", "*.sql"):
        all_files.extend(directory.glob(pattern))
    files = sorted(set(all_files), key=lambda p: p.stat().st_mtime, reverse=True)
    limit = await _retention_limit_for_type(backup_type, db)
    for old_file in files[limit:]:
        try:
            old_file.unlink()
        except Exception:
            pass


async def _apply_local_retention(backup_type: str, db: AsyncSession) -> None:
    local_dir = APP_DATA_DIR / "backups" / "local"
    await _apply_retention_to_directory(local_dir, backup_type, db)


async def _mirror_backup_to_sync_folder(local_path: Path, db: AsyncSession) -> tuple[str, str]:
    """
    Copie la sauvegarde dans le dossier Google Drive local (synchronisé).
    Note : ceci est une copie vers un dossier local synchronisé par le client
    Google Drive — ce n'est pas un upload direct vers l'API Google Drive.
    La disponibilité cloud dépend du client Drive étant installé et connecté.
    """
    settings = await _get_backup_settings_impl(db)
    sync_folder_raw = settings["gdrive_backup_dir"]
    if not sync_folder_raw:
        return "", "local-only"
    target_dir = Path(sync_folder_raw)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / local_path.name
    if str(target.resolve()) != str(local_path.resolve()):
        # Copie atomique : écriture dans un fichier temporaire puis renommage
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(
            dir=target_dir, delete=False, suffix=".tmp"
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            await asyncio.to_thread(shutil.copy2, local_path, tmp_path)
            await asyncio.to_thread(tmp_path.replace, target)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    return local_path.name, "google-drive-folder"


async def _apply_sync_folder_retention(backup_type: str, db: AsyncSession) -> None:
    settings = await _get_backup_settings_impl(db)
    sync_folder_raw = settings["gdrive_backup_dir"]
    if not sync_folder_raw:
        return
    target_dir = Path(sync_folder_raw)
    if not target_dir.exists():
        return
    await _apply_retention_to_directory(target_dir, backup_type, db)


async def run_pending_backup_jobs(limit: int = 3) -> int:
    with BACKGROUND_LOCK:
        BACKGROUND_STATE["last_run_ts"] = time.time()
    processed = 0

    async with get_async_sessionmaker()() as session:
        jobs_res = await session.execute(
            text("""
            SELECT *
            FROM backup_jobs
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT :limit
            """),
            {"limit": int(limit)},
        )
        jobs = [dict(row._mapping) for row in jobs_res.all()]

        for job in jobs:
            processed += 1
            await session.execute(
                text("UPDATE backup_jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": job["id"]}
            )
            await session.commit()

            sync_file_name = ""
            details = "local-only"
            try:
                local_path = Path(job["local_path"])
                if str(job["local_path"]) == BACKUP_CREATE_IN_WORKER:
                    from app.core.storage import capture_local_backup_snapshot

                    local_path = await asyncio.to_thread(capture_local_backup_snapshot, str(job["reason"] or "manual"))
                    await session.execute(
                        text("UPDATE backup_jobs SET local_path = :local_path WHERE id = :id"),
                        {"local_path": str(local_path), "id": job["id"]}
                    )
                if not local_path.exists():
                    raise FileNotFoundError(f"Sauvegarde locale introuvable: {local_path}")
                checksum = await asyncio.to_thread(_calculate_sha256, local_path)
                sync_file_name, details = await _mirror_backup_to_sync_folder(local_path, session)

                job_details = {
                    "sync_details": details,
                    "sha256": checksum,
                    "file_size": local_path.stat().st_size,
                    "backup_type": str(job["backup_type"] or "event")
                }

                await session.execute(
                    text("""
                    UPDATE backup_jobs
                    SET status = 'success',
                        finished_at = CURRENT_TIMESTAMP,
                        cloud_file_id = '',
                        cloud_file_name = :cloud_file_name,
                        context_json = :context_json,
                        error_message = ''
                    WHERE id = :id
                    """),
                    {
                        "cloud_file_name": sync_file_name,
                        "context_json": json.dumps(job_details),
                        "id": job["id"],
                    },
                )
                await _record_backup_run(job["id"], "success", cloud_file_name=sync_file_name, details=json.dumps(job_details), db=session)
                await session.commit()

                with BACKGROUND_LOCK:
                    BACKGROUND_STATE["last_backup_ts"] = time.time()
                await _apply_local_retention(str(job["backup_type"] or "event"), session)
                await _apply_sync_folder_retention(str(job["backup_type"] or "event"), session)

            except Exception as exc:
                await session.execute(
                    text("""
                    UPDATE backup_jobs
                    SET status = 'failed',
                        finished_at = CURRENT_TIMESTAMP,
                        error_message = :error_message
                    WHERE id = :id
                    """),
                    {
                        "error_message": str(exc),
                        "id": job["id"],
                    },
                )
                await _record_backup_run(job["id"], "failed", details=str(exc), db=session)
                await session.commit()
                logger.exception("Backup job %s failed", job["id"])

    return processed


async def run_deferred_event_backup(*, force: bool = False, reason: str = "deferred_event") -> Path | None:
    from app.core.storage import (
        capture_local_backup_snapshot,
        clear_backup_needed,
        get_pending_backup_marker,
    )

    marker = await asyncio.to_thread(get_pending_backup_marker)
    if not marker:
        return None
    marked_at_raw = str(marker.get("marked_at") or "")
    marked_at = None
    if marked_at_raw:
        try:
            marked_at = datetime.fromisoformat(marked_at_raw)
        except Exception:
            marked_at = None
    if not force and marked_at is not None:
        age_seconds = (datetime.now() - marked_at).total_seconds()
        if age_seconds < _event_backup_interval_seconds():
            return None

    backup_path = await asyncio.to_thread(capture_local_backup_snapshot, reason)
    async with get_async_sessionmaker()() as session:
        await _enqueue_backup_upload_impl(
            reason,
            "event",
            backup_path,
            requested_by_user_id=None,
            meta={
                "deferred": True,
                "trigger_reason": str(marker.get("reason") or ""),
                "marked_at": marked_at_raw,
            },
            db=session,
        )
        await session.commit()

    await asyncio.to_thread(clear_backup_needed)
    audit_event(
        action="backup_deferred_event",
        entity_type="backup",
        entity_id=backup_path.name,
        source="system",
        after={"filename": backup_path.name, "kind": "event", "deferred": True},
        meta={"trigger_reason": str(marker.get("reason") or ""), "marked_at": marked_at_raw},
    )
    return backup_path


def _acquire_postgres_scheduler_lock():
    with BACKGROUND_LOCK:
        if BACKGROUND_STATE.get("leader_conn") is not None:
            return True
    try:
        leader_conn = connect_database(DATABASE_URL)
        row = leader_conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (SCHEDULER_LOCK_ID,)).fetchone()
        locked = bool(row["locked"] if hasattr(row, "keys") else row[0])
        if locked:
            with BACKGROUND_LOCK:
                BACKGROUND_STATE["leader_conn"] = leader_conn
            return True
        leader_conn.close()
    except Exception:
        logger.exception("Unable to acquire scheduler leader lock")
    return False


async def trigger_nightly_snapshot_if_due() -> bool:
    async with get_async_sessionmaker()() as session:
        settings = await _get_backup_settings_impl(session)
        snapshot_time = str(settings["backup_snapshot_time"] or "02:00")
        try:
            hour, minute = [int(part) for part in snapshot_time.split(":", 1)]
        except Exception:
            hour, minute = 2, 0
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if settings["backup_last_nightly_date"] == today:
            return False
        if (now.hour, now.minute) < (hour, minute):
            return False
        from app.core.storage import capture_local_backup_snapshot

        backup_path = await asyncio.to_thread(capture_local_backup_snapshot, "nightly_snapshot")
        await _enqueue_backup_upload_impl("nightly_snapshot", "nightly", backup_path, None, {"scheduled": True}, db=session)
        from app.core.storage import clear_backup_needed

        await asyncio.to_thread(clear_backup_needed)
        await _set_setting_db("backup_last_nightly_date", today, session)
        await session.commit()

    audit_event(
        action="backup_schedule_run",
        entity_type="backup",
        entity_id=str(backup_path.name),
        source="system",
        after={"filename": backup_path.name, "kind": "nightly"},
    )
    return True


async def _purge_old_logs() -> None:
    """Purge performance/error/system logs older than 7 days to prevent table bloat."""
    try:
        ALLOWED_LOG_TABLES = {"performance_logs", "error_logs", "system_logs"}
        async with get_async_sessionmaker()() as session:
            for table in ("performance_logs", "error_logs", "system_logs"):
                if table not in ALLOWED_LOG_TABLES:
                    raise ValueError(f"Table {table} is not allowed for log purge")
                await session.execute(text(f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '7 days'"))
            await session.commit()
    except Exception:
        logger.debug("Log purge skipped (table may not exist yet)")

    # Nettoyer les clés d'idempotence expirées (> 7 jours) pour éviter la croissance illimitée
    try:
        from app.core.idempotency import cleanup_expired_idempotency_keys
        await cleanup_expired_idempotency_keys(max_age_days=7)
    except Exception:
        logger.debug("Idempotency cleanup skipped (table may not exist yet)")


async def _weekly_vacuum() -> None:
    """Run VACUUM ANALYZE weekly to reclaim space and update statistics."""
    now = datetime.now()
    if now.weekday() != 6:  # Only run on Sunday
        return
    today = now.strftime("%Y-%m-%d")
    async with get_async_sessionmaker()() as session:
        last_vacuum = await _get_setting_db("last_vacuum_date", "", session)
    if last_vacuum == today:
        return
    if now.hour < 3: # Run after 3 AM
        return

    try:
        from app.core.config import DATABASE_URL
        from sqlalchemy import create_engine

        # VACUUM cannot run inside a transaction block, we need autocommit
        url = DATABASE_URL
        if url.startswith("postgresql://"):
            url = "postgresql+pg8000://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            url = "postgresql+pg8000://" + url[len("postgres://"):]

        def run_vacuum():
            engine = create_engine(url, isolation_level="AUTOCOMMIT")
            with engine.connect() as conn:
                conn.execute(text("VACUUM ANALYZE"))
            engine.dispose()

        await asyncio.to_thread(run_vacuum)
        async with get_async_sessionmaker()() as session:
            await _set_setting_db("last_vacuum_date", today, session)
            await session.commit()
        logger.info("Weekly VACUUM ANALYZE completed successfully.")
    except Exception as e:
        logger.warning("Weekly VACUUM ANALYZE failed: %s", e)


async def _safe_run_async(task_name: str, func, *args, **kwargs) -> bool:
    """Run an async background task, returning True on success."""
    try:
        await func(*args, **kwargs)
        return True
    except Exception:
        logger.exception("Background task '%s' failed", task_name)
        return False


def _background_loop(app) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def main_loop():
        import random
        consecutive_failures = 0
        while True:
            if _shutdown_requested():
                logger.info("Scheduler: shutdown demandé, arrêt.")
                break
            success = True
            success &= await _safe_run_async("run_deferred_event_backup", run_deferred_event_backup)
            success &= await _safe_run_async("run_pending_backup_jobs", run_pending_backup_jobs, limit=4)
            success &= await _safe_run_async("trigger_nightly_snapshot_if_due", trigger_nightly_snapshot_if_due)
            success &= await _safe_run_async("purge_old_logs", _purge_old_logs)
            success &= await _safe_run_async("weekly_vacuum", _weekly_vacuum)

            # Log pool stats every ~15 minutes (20 loops of 45s)
            with BACKGROUND_LOCK:
                loop_counter = BACKGROUND_STATE.get("loop_counter", 0) + 1
                BACKGROUND_STATE["loop_counter"] = loop_counter
            if loop_counter % 20 == 0:
                from app.core.db import postgres_pool_status
                stats = postgres_pool_status(DATABASE_URL)
                logger.debug("PG Pool status: %s", stats)

            # Call check_stock_alerts every 30 minutes (40 loops of 45s)
            if loop_counter == 1 or loop_counter % 40 == 0:
                from app.services.alert_service import check_stock_alerts
                await _safe_run_async("check_stock_alerts", check_stock_alerts)

            with BACKGROUND_LOCK:
                BACKGROUND_STATE["last_run_ts"] = time.time()

            if not success:
                consecutive_failures += 1
                sleep_time = min(300.0, 45.0 * (1.5 ** consecutive_failures) + random.uniform(0.0, 10.0))
            else:
                consecutive_failures = 0
                sleep_time = 45.0

            # Incremental sleep to check shutdown_requested quickly
            for _ in range(int(sleep_time)):
                if _shutdown_requested():
                    break
                await asyncio.sleep(1.0)
            else:
                fraction = sleep_time - int(sleep_time)
                if fraction > 0 and not _shutdown_requested():
                    await asyncio.sleep(fraction)

    try:
        loop.run_until_complete(main_loop())
    finally:
        loop.close()


def start_background_services(app=None) -> None:
    with BACKGROUND_LOCK:
        if BACKGROUND_STATE["started"]:
            return
        testing = bool(getattr(app, "debug", False)) if app is not None else False
        if testing or os.getenv("FAB_DISABLE_BACKGROUND_JOBS", "0") == "1":
            return
        try:
            from app.core.config import configured_worker_count

            multi_worker = configured_worker_count() > 1
        except Exception:
            multi_worker = False
        scheduler_owner = os.getenv("FAB_BACKUP_SCHEDULER", "").strip().lower() in {"1", "true", "yes", "on"}
        if multi_worker and not scheduler_owner:
            logger.warning("Backup scheduler disabled in multi-worker runtime; run one FAB_BACKUP_SCHEDULER=1 process.")
            return
        if not _acquire_postgres_scheduler_lock():
            logger.info("Backup scheduler skipped: PostgreSQL advisory lock is held by another process.")
            return
        BACKGROUND_STATE["started"] = True
        thread = threading.Thread(target=_background_loop, args=(app,), name="fab-backup-scheduler", daemon=True)
        BACKGROUND_STATE["thread"] = thread
        thread.start()


def shutdown_background_services(app=None) -> None:
    global BACKGROUND_STATE
    with BACKGROUND_LOCK:
        BACKGROUND_STATE["shutdown_requested"] = True
        conn = BACKGROUND_STATE.get("leader_conn")
        if conn is not None:
            try:
                conn.execute("SELECT pg_advisory_unlock(%s)", (SCHEDULER_LOCK_ID,))
                conn.close()
            except Exception:
                pass
            BACKGROUND_STATE["leader_conn"] = None
    thread = BACKGROUND_STATE.get("thread")
    if thread and thread.is_alive():
        thread.join(timeout=10)
    logger.info("Background services stopped.")
