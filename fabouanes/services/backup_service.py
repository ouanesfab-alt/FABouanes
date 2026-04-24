from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fabouanes.fastapi_compat import current_app

from fabouanes.config import APP_DATA_DIR, DATABASE_URL
from fabouanes.core.audit import audit_event
from fabouanes.core.db_access import execute_db, get_setting, query_db, set_setting
from fabouanes.db import connect_database
from fabouanes.postgres_support import POSTGRES_BACKUP_SUFFIX, SQLITE_IMPORT_FILE_NAME

SCHEDULER_LOCK_ID = 48216731
SQLITE_IMPORT_PATH_HINT = APP_DATA_DIR / SQLITE_IMPORT_FILE_NAME
BACKGROUND_STATE = {
    "started": False,
    "thread": None,
    "leader_conn": None,
}


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
    files = sorted(directory.glob(f"*{POSTGRES_BACKUP_SUFFIX}"), key=lambda path: path.stat().st_mtime, reverse=True)
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
    sync_folder_raw = get_backup_settings()["gdrive_backup_dir"]
    if not sync_folder_raw:
        return "", "local-only"
    target_dir = Path(sync_folder_raw)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / local_path.name
    if str(target.resolve()) != str(local_path.resolve()):
        target.write_bytes(local_path.read_bytes())
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
            if not local_path.exists():
                raise FileNotFoundError(f"Sauvegarde locale introuvable: {local_path}")
            sync_file_name, details = _mirror_backup_to_sync_folder(local_path)
            execute_db(
                """
                UPDATE backup_jobs
                SET status = 'success',
                    finished_at = CURRENT_TIMESTAMP,
                    cloud_file_id = '',
                    cloud_file_name = ?,
                    error_message = ''
                WHERE id = ?
                """,
                (sync_file_name, job["id"]),
            )
            _record_backup_run(job["id"], "success", cloud_file_name=sync_file_name, details=details)
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
            current_app.logger.exception("Backup job %s failed", job["id"])
    return processed


def _acquire_postgres_scheduler_lock():
    if BACKGROUND_STATE.get("leader_conn") is not None:
        return True
    try:
        leader_conn = connect_database(DATABASE_URL, SQLITE_IMPORT_PATH_HINT)
        row = leader_conn.execute("SELECT pg_try_advisory_lock(?) AS locked", (SCHEDULER_LOCK_ID,)).fetchone()
        locked = bool(row["locked"] if hasattr(row, "keys") else row[0])
        if locked:
            BACKGROUND_STATE["leader_conn"] = leader_conn
            return True
        leader_conn.close()
    except Exception:
        current_app.logger.exception("Unable to acquire scheduler leader lock")
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
    from fabouanes.core.storage import capture_local_backup_snapshot

    backup_path = capture_local_backup_snapshot("nightly_snapshot")
    enqueue_backup_upload("nightly_snapshot", "nightly", backup_path, meta={"scheduled": True})
    set_setting("backup_last_nightly_date", today)
    audit_event(
        action="backup_schedule_run",
        entity_type="backup",
        entity_id=str(backup_path.name),
        source="system",
        after={"filename": backup_path.name, "kind": "nightly"},
    )
    return True


def _background_loop(app) -> None:
    while True:
        try:
            with app.app_context():
                if not _acquire_postgres_scheduler_lock():
                    time.sleep(45)
                    continue
                run_pending_backup_jobs(limit=4)
                trigger_nightly_snapshot_if_due()
        except Exception:
            with app.app_context():
                current_app.logger.exception("Backup scheduler cycle failed")
        time.sleep(45)


def start_background_services(app) -> None:
    if BACKGROUND_STATE["started"]:
        return
    if app.config.get("TESTING") or os.getenv("FAB_DISABLE_BACKGROUND_JOBS", "0") == "1":
        return
    BACKGROUND_STATE["started"] = True
    thread = threading.Thread(target=_background_loop, args=(app,), name="fab-backup-scheduler", daemon=True)
    BACKGROUND_STATE["thread"] = thread
    thread.start()
