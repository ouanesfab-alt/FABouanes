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
from app.core.db_access import execute_db, get_setting, query_db, set_setting
from app.core.db import connect_database


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


def get_backup_settings() -> dict[str, Any]:
    return {
        "gdrive_backup_dir": get_setting("gdrive_backup_dir", ""),
        "backup_snapshot_time": get_setting("backup_snapshot_time", "02:00"),
        "backup_local_retention": int(get_setting("backup_local_retention", "30") or 30),
        "backup_event_retention": int(get_setting("backup_event_retention", "100") or 100),
        "backup_last_nightly_date": get_setting("backup_last_nightly_date", ""),
    }


def save_backup_configuration(payload: dict[str, Any]) -> None:
    fields = {
        "gdrive_backup_dir": str(payload.get("gdrive_backup_dir", "") or "").strip(),
        "backup_snapshot_time": str(payload.get("backup_snapshot_time", "02:00") or "02:00").strip(),
        "backup_local_retention": str(payload.get("backup_local_retention", 30) or 30).strip(),
        "backup_event_retention": str(payload.get("backup_event_retention", 100) or 100).strip(),
    }
    for key, value in fields.items():
        set_setting(key, value)


def enqueue_backup_upload(
    reason: str,
    backup_type: str,
    local_path: str | Path,
    *,
    requested_by_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    return execute_db(
        """
        INSERT INTO backup_jobs (
            reason,
            backup_type,
            local_path,
            requested_by_user_id,
            status,
            context_json,
            created_at
        ) VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
        """,
        (
            reason,
            backup_type,
            str(local_path),
            requested_by_user_id,
            "" if meta is None else json.dumps(meta, ensure_ascii=True, sort_keys=True),
        ),
    )


def enqueue_backup_snapshot(
    reason: str,
    backup_type: str = "manual",
    *,
    requested_by_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    return enqueue_backup_upload(
        reason,
        backup_type,
        BACKUP_CREATE_IN_WORKER,
        requested_by_user_id=requested_by_user_id,
        meta={"create_snapshot": True, **(meta or {})},
    )


def list_backup_jobs(limit: int = 40):
    return query_db(
        """
        SELECT bj.*,
               u.username AS requested_by_username
        FROM backup_jobs bj
        LEFT JOIN users u ON u.id = bj.requested_by_user_id
        ORDER BY bj.id DESC
        LIMIT ?
        """,
        (int(limit),),
    )


def _record_backup_run(job_id: int, status: str, *, cloud_file_name: str = "", details: str = "") -> None:
    execute_db(
        """
        INSERT INTO backup_runs (job_id, status, cloud_file_id, cloud_file_name, details_json, started_at, finished_at)
        VALUES (?, ?, '', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (job_id, status, cloud_file_name, details),
    )


def _retention_limit_for_type(backup_type: str) -> int:
    settings = get_backup_settings()
    return settings["backup_local_retention"] if backup_type == "nightly" else settings["backup_event_retention"]


def _apply_retention_to_directory(directory: Path, backup_type: str) -> None:
    # Gestion des deux extensions : .sql.gz (nouveau) et .sql (legacy)
    all_files = []
    for pattern in ("*.sql.gz", "*.sql"):
        all_files.extend(directory.glob(pattern))
    files = sorted(set(all_files), key=lambda p: p.stat().st_mtime, reverse=True)
    limit = _retention_limit_for_type(backup_type)
    for old_file in files[limit:]:
        try:
            old_file.unlink()
        except Exception:
            pass


def _apply_local_retention(backup_type: str) -> None:
    local_dir = APP_DATA_DIR / "backups" / "local"
    _apply_retention_to_directory(local_dir, backup_type)


def _mirror_backup_to_sync_folder(local_path: Path) -> tuple[str, str]:
    """
    Copie la sauvegarde dans le dossier Google Drive local (synchronisé).
    Note : ceci est une copie vers un dossier local synchronisé par le client
    Google Drive — ce n'est pas un upload direct vers l'API Google Drive.
    La disponibilité cloud dépend du client Drive étant installé et connecté.
    """
    sync_folder_raw = get_backup_settings()["gdrive_backup_dir"]
    if not sync_folder_raw:
        return "", "local-only"
    target_dir = Path(sync_folder_raw)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / local_path.name
    if str(target.resolve()) != str(local_path.resolve()):
        # Copie atomique : écriture dans un fichier temporaire puis renommage
        import tempfile, shutil
        with tempfile.NamedTemporaryFile(
            dir=target_dir, delete=False, suffix=".tmp"
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            shutil.copy2(local_path, tmp_path)
            tmp_path.replace(target)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    return local_path.name, "google-drive-folder"


def _apply_sync_folder_retention(backup_type: str) -> None:
    sync_folder_raw = get_backup_settings()["gdrive_backup_dir"]
    if not sync_folder_raw:
        return
    target_dir = Path(sync_folder_raw)
    if not target_dir.exists():
        return
    _apply_retention_to_directory(target_dir, backup_type)


def run_pending_backup_jobs(limit: int = 3) -> int:
    with BACKGROUND_LOCK:
        BACKGROUND_STATE["last_run_ts"] = time.time()
    processed = 0

    jobs = query_db(
        """
        SELECT *
        FROM backup_jobs
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT ?
        """,
        (int(limit),),
    )
    for job in jobs:
        processed += 1
        execute_db("UPDATE backup_jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?", (job["id"],))
        sync_file_name = ""
        details = "local-only"
        try:
            local_path = Path(job["local_path"])
            if str(job["local_path"]) == BACKUP_CREATE_IN_WORKER:
                from app.core.storage import capture_local_backup_snapshot
 
                local_path = capture_local_backup_snapshot(str(job["reason"] or "manual"))
                execute_db("UPDATE backup_jobs SET local_path = ? WHERE id = ?", (str(local_path), job["id"]))
            if not local_path.exists():
                raise FileNotFoundError(f"Sauvegarde locale introuvable: {local_path}")
            checksum = _calculate_sha256(local_path)
            sync_file_name, details = _mirror_backup_to_sync_folder(local_path)
            
            job_details = {
                "sync_details": details,
                "sha256": checksum,
                "file_size": local_path.stat().st_size,
                "backup_type": str(job["backup_type"] or "event")
            }
            
            execute_db(
                """
                UPDATE backup_jobs
                SET status = 'success',
                    finished_at = CURRENT_TIMESTAMP,
                    cloud_file_id = '',
                    cloud_file_name = ?,
                    context_json = ?,
                    error_message = ''
                WHERE id = ?
                """,
                (sync_file_name, json.dumps(job_details), job["id"]),
            )
            _record_backup_run(job["id"], "success", cloud_file_name=sync_file_name, details=json.dumps(job_details))
            with BACKGROUND_LOCK:
                BACKGROUND_STATE["last_backup_ts"] = time.time()
            _apply_local_retention(str(job["backup_type"] or "event"))

            _apply_sync_folder_retention(str(job["backup_type"] or "event"))

        except Exception as exc:
            execute_db(
                """
                UPDATE backup_jobs
                SET status = 'failed',
                    finished_at = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE id = ?
                """,
                (str(exc), job["id"]),
            )
            _record_backup_run(job["id"], "failed", details=str(exc))
            logger.exception("Backup job %s failed", job["id"])
    return processed


def run_deferred_event_backup(*, force: bool = False, reason: str = "deferred_event") -> Path | None:
    from app.core.storage import (
        capture_local_backup_snapshot,
        clear_backup_needed,
        get_pending_backup_marker,
    )

    marker = get_pending_backup_marker()
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

    backup_path = capture_local_backup_snapshot(reason)
    enqueue_backup_upload(
        reason,
        "event",
        backup_path,
        meta={
            "deferred": True,
            "trigger_reason": str(marker.get("reason") or ""),
            "marked_at": marked_at_raw,
        },
    )
    clear_backup_needed()
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
        row = leader_conn.execute("SELECT pg_try_advisory_lock(?) AS locked", (SCHEDULER_LOCK_ID,)).fetchone()
        locked = bool(row["locked"] if hasattr(row, "keys") else row[0])
        if locked:
            with BACKGROUND_LOCK:
                BACKGROUND_STATE["leader_conn"] = leader_conn
            return True
        leader_conn.close()
    except Exception:
        logger.exception("Unable to acquire scheduler leader lock")
    return False


def trigger_nightly_snapshot_if_due() -> bool:
    settings = get_backup_settings()
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

    backup_path = capture_local_backup_snapshot("nightly_snapshot")
    enqueue_backup_upload("nightly_snapshot", "nightly", backup_path, meta={"scheduled": True})
    from app.core.storage import clear_backup_needed

    clear_backup_needed()
    set_setting("backup_last_nightly_date", today)
    audit_event(
        action="backup_schedule_run",
        entity_type="backup",
        entity_id=str(backup_path.name),
        source="system",
        after={"filename": backup_path.name, "kind": "nightly"},
    )
    return True


def _purge_old_logs() -> None:
    """Purge performance/error/system logs older than 7 days to prevent table bloat."""
    try:
        from app.core.db_access import execute_db
        for table in ("performance_logs", "error_logs", "system_logs"):
            execute_db(f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '7 days'")
    except Exception:
        logger.debug("Log purge skipped (table may not exist yet)")


def _weekly_vacuum() -> None:
    """Run VACUUM ANALYZE weekly to reclaim space and update statistics."""
    now = datetime.now()
    if now.weekday() != 6:  # Only run on Sunday
        return
    today = now.strftime("%Y-%m-%d")
    if get_setting("last_vacuum_date", "") == today:
        return
    if now.hour < 3: # Run after 3 AM
        return
    
    try:
        from app.core.config import DATABASE_URL
        from sqlalchemy import create_engine, text
        
        # VACUUM cannot run inside a transaction block, we need autocommit
        url = DATABASE_URL
        if url.startswith("postgresql://"):
            url = "postgresql+pg8000://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            url = "postgresql+pg8000://" + url[len("postgres://"):]
            
        engine = create_engine(url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text("VACUUM ANALYZE"))
        engine.dispose()
        
        set_setting("last_vacuum_date", today)
        logger.info("Weekly VACUUM ANALYZE completed successfully.")
    except Exception as e:
        logger.warning("Weekly VACUUM ANALYZE failed: %s", e)


def _safe_run(task_name: str, func, *args, **kwargs) -> bool:
    """Run a background task, rolling back on error so PostgreSQL stays healthy."""
    try:
        func(*args, **kwargs)
        return True
    except Exception:
        logger.exception("Background task '%s' failed", task_name)
        try:
            from app.core.db_access import get_db
            get_db().rollback()
        except Exception:
            pass
        return False


def _background_loop(app) -> None:
    import random
    consecutive_failures = 0
    while True:
        if BACKGROUND_STATE.get("shutdown_requested"):
            logger.info("Scheduler: shutdown demandé, arrêt.")
            break
        success = True
        success &= _safe_run("run_deferred_event_backup", run_deferred_event_backup)
        success &= _safe_run("run_pending_backup_jobs", run_pending_backup_jobs, limit=4)
        success &= _safe_run("trigger_nightly_snapshot_if_due", trigger_nightly_snapshot_if_due)
        success &= _safe_run("purge_old_logs", _purge_old_logs)
        success &= _safe_run("weekly_vacuum", _weekly_vacuum)
        
        # Log pool stats every ~15 minutes (20 loops of 45s)
        loop_counter = BACKGROUND_STATE.get("loop_counter", 0) + 1
        BACKGROUND_STATE["loop_counter"] = loop_counter
        if loop_counter % 20 == 0:
            from app.core.db_access import postgres_pool_status
            stats = postgres_pool_status(DATABASE_URL)
            logger.debug("PG Pool status: %s", stats)

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
            if BACKGROUND_STATE.get("shutdown_requested"):
                break
            time.sleep(1.0)
        else:
            fraction = sleep_time - int(sleep_time)
            if fraction > 0 and not BACKGROUND_STATE.get("shutdown_requested"):
                time.sleep(fraction)


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
    thread = BACKGROUND_STATE.get("thread")
    if thread and thread.is_alive():
        thread.join(timeout=10)
    logger.info("Background services stopped.")
