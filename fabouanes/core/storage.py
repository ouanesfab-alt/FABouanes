from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flask import g

from fabouanes.config import APP_DATA_DIR, BUNDLED_DB_PATH, DATABASE_URL
from fabouanes.core.activity import write_text_log
from fabouanes.core.db_access import get_setting

DB_PATH = APP_DATA_DIR / "database.db"
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
    if not DB_PATH.exists() and BUNDLED_DB_PATH.exists():
        shutil.copy2(BUNDLED_DB_PATH, DB_PATH)


def capture_local_backup_snapshot(reason: str = "manual") -> Path:
    ensure_runtime_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "sql" if DATABASE_URL.lower().startswith("postgres") else "db"
    filename = f"database_{stamp}_{reason.replace(' ', '_')}.{suffix}"
    target = LOCAL_BACKUP_DIR / filename
    db = g.get("db")
    if db is not None:
        db.commit()
    if DATABASE_URL.lower().startswith("postgres"):
        target.write_text("-- Backup PostgreSQL logique non implemente automatiquement dans cette version.\n", encoding="utf-8")
    else:
        shutil.copy2(DB_PATH, target)
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
    if DATABASE_URL.lower().startswith("postgres"):
        raise RuntimeError("La restauration PostgreSQL automatique n'est pas prise en charge dans cette version.")
    db = g.pop("db", None)
    if db is not None:
        db.close()
    shutil.copy2(path_str, DB_PATH)


def get_google_drive_sync_dir() -> Path | None:
    raw = get_setting("gdrive_backup_dir", "").strip()
    if not raw:
        return None
    return Path(raw)


def list_restore_backups() -> list[dict[str, str]]:
    backups: list[dict[str, str]] = []
    pattern = "*.sql" if DATABASE_URL.lower().startswith("postgres") else "*.db"
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
