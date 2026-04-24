from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fabouanes.fastapi_compat import g

from fabouanes.config import APP_DATA_DIR, DATABASE_URL
from fabouanes.core.activity import write_text_log
from fabouanes.core.db_access import get_setting
from fabouanes.postgres_support import (
    POSTGRES_BACKUP_SUFFIX,
    SQLITE_IMPORT_FILE_NAME,
    create_postgres_backup,
    restore_postgres_backup,
)

SQLITE_IMPORT_PATH_HINT = APP_DATA_DIR / SQLITE_IMPORT_FILE_NAME
BACKUP_DIR = APP_DATA_DIR / "backups"
LOCAL_BACKUP_DIR = BACKUP_DIR / "local"
LOG_DIR = APP_DATA_DIR / "logs"
REPORT_DIR = APP_DATA_DIR / "reports_generated"
NOTES_DIR = APP_DATA_DIR / "notes"
PDF_READER_DIR = APP_DATA_DIR / "pdf_reader"
IMPORT_DIR = APP_DATA_DIR / "imports"


def ensure_runtime_dirs() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    PDF_READER_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)


def capture_local_backup_snapshot(reason: str = "manual") -> Path:
    ensure_runtime_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"database_{stamp}_{reason.replace(' ', '_')}{POSTGRES_BACKUP_SUFFIX}"
    target = LOCAL_BACKUP_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    db = g.get("db")
    if db is not None:
        db.commit()
    create_postgres_backup(DATABASE_URL, SQLITE_IMPORT_PATH_HINT, target)
    return target


def backup_database(reason: str = "manual", backup_type: str = "event") -> Path:
    target = capture_local_backup_snapshot(reason)
    try:
        from fabouanes.services.backup_service import enqueue_backup_upload

        requested_by = None
        if getattr(g, "user", None):
            requested_by = int(g.user["id"])
        enqueue_backup_upload(reason, backup_type, target, requested_by_user_id=requested_by)
    except Exception as cloud_exc:
        write_text_log("errors.log", f"backup queue failed: {cloud_exc}")
    return target


def restore_database_from(path_str: str) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
    restore_postgres_backup(DATABASE_URL, SQLITE_IMPORT_PATH_HINT, path_str)


def get_google_drive_sync_dir() -> Path | None:
    raw = get_setting("gdrive_backup_dir", "").strip()
    if not raw:
        return None
    return Path(raw)


def list_restore_backups() -> list[dict[str, str]]:
    backups: list[dict[str, str]] = []
    pattern = f"*{POSTGRES_BACKUP_SUFFIX}"
    seen_names: set[str] = set()
    for path in sorted(LOCAL_BACKUP_DIR.glob(pattern), reverse=True):
        seen_names.add(path.name)
        backups.append(
            {
                "value": f"local:{path.name}",
                "name": path.name,
                "source": "local",
                "label": f"Local - {path.name}",
            }
        )
    sync_dir = get_google_drive_sync_dir()
    if sync_dir and sync_dir.exists():
        for path in sorted(sync_dir.glob(pattern), reverse=True):
            if path.name in seen_names:
                continue
            backups.append(
                {
                    "value": f"drive:{path.name}",
                    "name": path.name,
                    "source": "drive",
                    "label": f"Google Drive - {path.name}",
                }
            )
    return backups


def resolve_backup_path(backup_value: str) -> Path | None:
    raw = (backup_value or "").strip()
    if not raw:
        return None
    if ":" in raw:
        source, name = raw.split(":", 1)
    else:
        source, name = "local", raw
    if source == "local":
        path = LOCAL_BACKUP_DIR / name
        return path if path.exists() else None
    if source in {"drive", "cloud"}:
        sync_dir = get_google_drive_sync_dir()
        if sync_dir:
            path = sync_dir / name
            return path if path.exists() else None
    return None
