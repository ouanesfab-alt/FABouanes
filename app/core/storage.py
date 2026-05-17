from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.request_state import get_state_value

from app.core.config import APP_DATA_DIR, BUNDLED_DB_PATH, DATABASE_URL
from app.core.activity import write_text_log
from app.core.db_access import execute_db, get_setting

DB_PATH = APP_DATA_DIR / "database.db"
BACKUP_DIR = APP_DATA_DIR / "backups"
LOCAL_BACKUP_DIR = BACKUP_DIR / "local"
LOG_DIR = APP_DATA_DIR / "logs"
REPORT_DIR = APP_DATA_DIR / "reports_generated"
NOTES_DIR = APP_DATA_DIR / "notes"
PDF_READER_DIR = APP_DATA_DIR / "pdf_reader"
IMPORT_DIR = APP_DATA_DIR / "imports"
BACKUP_NEEDED_SETTING = "backup_needed"


def _request_db():
    return get_state_value("db")


def _current_user_id() -> int | None:
    user = get_state_value("user")
    if user:
        try:
            return int(user["id"])
        except Exception:
            return None
    return None


def _event_backups_enabled() -> bool:
    return os.environ.get("FAB_ENABLE_EVENT_BACKUPS", "0").strip().lower() in {"1", "true", "yes", "on"}


def mark_backup_needed(reason: str = "event") -> None:
    payload = {
        "reason": str(reason or "event"),
        "marked_at": datetime.now().isoformat(timespec="seconds"),
    }
    execute_db(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """,
        (BACKUP_NEEDED_SETTING, json.dumps(payload, ensure_ascii=True, sort_keys=True)),
    )


def get_pending_backup_marker() -> dict:
    raw = get_setting(BACKUP_NEEDED_SETTING, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {"reason": raw, "marked_at": ""}
    return payload if isinstance(payload, dict) else {}


def clear_backup_needed() -> None:
    execute_db(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, '', CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value='', updated_at=CURRENT_TIMESTAMP
        """,
        (BACKUP_NEEDED_SETTING,),
    )


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
    db = _request_db()
    if db is not None:
        db.commit()
    if DATABASE_URL.lower().startswith("postgres"):
        from urllib.parse import urlparse
        import subprocess
        
        parsed = urlparse(DATABASE_URL)
        username = parsed.username or "postgres"
        password = parsed.password or ""
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5432
        database = parsed.path.lstrip("/")
        
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
            
        success = False
        try:
            cmd = ["pg_dump", "-h", host, "-p", str(port), "-U", username, "-F", "p", "-f", str(target), database]
            subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            success = True
        except Exception:
            success = False
            
        if not success:
            # Fallback table-by-table logical backup using Python pg8000
            try:
                from app.core.db import connect_database
                conn = connect_database(DATABASE_URL)
                try:
                    cur = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
                    tables = [row[0] if hasattr(row, "keys") else row[0] for row in cur.fetchall()]
                    cur.close()
                    
                    with open(target, "w", encoding="utf-8") as f:
                        f.write("-- FABOuanes Fallback SQL Dump\n")
                        f.write(f"-- Created at: {datetime.now().isoformat()}\n\n")
                        f.write("SET session_replication_role = 'replica';\n\n")
                        for table in tables:
                            cur = conn.execute(
                                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                                (table,)
                            )
                            cols = [r[0] if hasattr(r, "keys") else r[0] for r in cur.fetchall()]
                            cur.close()
                            
                            f.write(f"TRUNCATE TABLE {table} CASCADE;\n")
                            cur = conn.execute(f"SELECT * FROM {table}")
                            rows = cur.fetchall()
                            cur.close()
                            
                            for row in rows:
                                vals = []
                                for col in cols:
                                    val = row[col]
                                    if val is None:
                                        vals.append("NULL")
                                    elif isinstance(val, (int, float)):
                                        vals.append(str(val))
                                    elif isinstance(val, bool):
                                        vals.append("TRUE" if val else "FALSE")
                                    else:
                                        escaped = str(val).replace("'", "''")
                                        vals.append(f"'{escaped}'")
                                cols_str = ", ".join(cols)
                                vals_str = ", ".join(vals)
                                f.write(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});\n")
                            f.write("\n")
                        f.write("SET session_replication_role = 'origin';\n")
                finally:
                    conn.close()
            except Exception as fe:
                target.write_text(f"-- PostgreSQL backup failed.\n-- fallback error: {fe}\n", encoding="utf-8")
    else:
        shutil.copy2(DB_PATH, target)
    return target


def backup_database(reason: str = "manual", backup_type: str = "event") -> Path:
    if backup_type == "event" and not _event_backups_enabled():
        mark_backup_needed(reason)
        return DB_PATH
    target = capture_local_backup_snapshot(reason)
    try:
        from app.services.backup_service import enqueue_backup_upload

        requested_by = _current_user_id()
        enqueue_backup_upload(reason, backup_type, target, requested_by_user_id=requested_by)
        if backup_type in {"manual", "nightly"}:
            clear_backup_needed()
    except Exception as cloud_exc:
        write_text_log("errors.log", f"backup queue failed: {cloud_exc}")
    return target


def restore_database_from(path_str: str) -> None:
    if DATABASE_URL.lower().startswith("postgres"):
        path = Path(path_str)
        verify_backup_file(path)
        
        from app.core.db import connect_database
        from app.core.db_compat import split_sql_script
        
        sql_content = path.read_text(encoding="utf-8")
        conn = connect_database(DATABASE_URL)
        try:
            for stmt in split_sql_script(sql_content):
                if stmt.strip():
                    conn.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Erreur lors de la restauration PostgreSQL : {e}") from e
        finally:
            conn.close()
        return
        
    verify_backup_file(Path(path_str))
    db = _request_db()
    if db is not None:
        db.close()
    shutil.copy2(path_str, DB_PATH)


def verify_backup_file(path: Path) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        raise RuntimeError("Fichier de sauvegarde introuvable.")
    if DATABASE_URL.lower().startswith("postgres"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                head = f.read(500)
            if "--" not in head and "CREATE" not in head and "INSERT" not in head and "SET" not in head:
                raise RuntimeError("Sauvegarde PostgreSQL invalide (format SQL non reconnu).")
        except Exception as e:
            raise RuntimeError(f"Sauvegarde PostgreSQL invalide: {e}")
        return {"ok": True, "engine": "postgres", "path": str(path)}
    try:
        conn = sqlite3.connect(str(path))
        try:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            if not row:
                raise RuntimeError("Sauvegarde SQLite invalide: table users manquante.")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                raise RuntimeError(f"Sauvegarde SQLite corrompue: {integrity[0] if integrity else 'inconnue'}")
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"Sauvegarde SQLite invalide: {exc}") from exc
    return {"ok": True, "engine": "sqlite", "path": str(path)}


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
