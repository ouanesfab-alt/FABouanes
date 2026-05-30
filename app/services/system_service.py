from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.core.config import APP_DATA_DIR, DATABASE_URL
from app.core.db import connect_database, postgres_pool_status
from app.core.activity import write_text_log
import asyncio
from app.core.db_access import execute_db_async, explain_query_plan, get_db, query_db_async
from app.core.storage import LOCAL_BACKUP_DIR, LOG_DIR, get_pending_backup_marker, list_restore_backups
from app.version import VERSION_LABEL


def _ok_status(ok: bool) -> str:
    return "OK" if ok else "Attention"


async def get_system_status() -> dict:
    db_ok = False
    db_message = ""
    try:
        await query_db_async("SELECT 1", (), one=True)
        db_ok = True
        db_message = "Connexion base disponible"
    except Exception as exc:
        db_message = str(exc)

    backups = list_restore_backups()
    latest_job = await query_db_async("SELECT * FROM backup_jobs ORDER BY id DESC LIMIT 1", (), one=True)
    index_count = 0
    plan_lines: list[str] = []
    try:
        index_row = await query_db_async(
            "SELECT COUNT(*) AS c FROM pg_indexes WHERE schemaname = current_schema() AND indexname LIKE 'idx_%'",
            (),
            one=True,
        )
        index_count = int(index_row["c"] if index_row else 0)
        query_plan = await asyncio.to_thread(explain_query_plan, "SELECT id, name FROM clients ORDER BY name LIMIT 50")
        for row in query_plan:
            row_dict = dict(row) if hasattr(row, "keys") else {}
            detail = row_dict.get("detail") or row_dict.get("plan") or next(iter(row_dict.values()), "") or str(row)
            plan_lines.append(str(detail))
    except Exception:
        _rollback_current_db()
        pass
    pending_marker = get_pending_backup_marker()
    data_dir = Path(APP_DATA_DIR)
    backup_dir = Path(LOCAL_BACKUP_DIR)
    log_dir = Path(LOG_DIR)
    latest_backup_file = next(iter(sorted(backup_dir.glob("*.sql"), reverse=True)), None) if backup_dir.exists() else None
    from app.services.backup_service import BACKGROUND_STATE
    write_status = await _probe_db_write()
    backup_write_status = _probe_dir_write(backup_dir)
    return {
        "version": VERSION_LABEL,
        "background_jobs": {
            "started": BACKGROUND_STATE.get("started", False),
            "last_run_at": datetime.fromtimestamp(BACKGROUND_STATE.get("last_run_ts", 0)).isoformat() if BACKGROUND_STATE.get("last_run_ts") else None,
            "last_backup_at": datetime.fromtimestamp(BACKGROUND_STATE.get("last_backup_ts", 0)).isoformat() if BACKGROUND_STATE.get("last_backup_ts") else None,
        },
        "database": {

            "ok": db_ok,
            "status": _ok_status(db_ok),
            "message": db_message,
            "engine": "PostgreSQL",
            "path": DATABASE_URL,
            "exists": True,
            "size_bytes": 0,
            "write_status": write_status,
            "pool": postgres_pool_status(DATABASE_URL),
        },
        "backups": {
            "ok": bool(backups) or bool(latest_job) or not pending_marker,
            "status": _ok_status(bool(backups) or bool(latest_job) or not pending_marker),
            "count": len(backups),
            "local_dir": str(backup_dir),
            "write_status": backup_write_status,
            "latest_file": latest_backup_file.name if latest_backup_file else "",
            "latest_file_at": datetime.fromtimestamp(latest_backup_file.stat().st_mtime).isoformat(timespec="seconds") if latest_backup_file else "",
            "latest_job_status": str(latest_job["status"]) if latest_job else "aucun job",
            "latest_job_reason": str(latest_job["reason"]) if latest_job else "",
            "pending_reason": str(pending_marker.get("reason", "")),
            "pending_since": str(pending_marker.get("marked_at", "")),
        },
        "paths": {
            "data_dir": str(data_dir),
            "log_dir": str(log_dir),
            "data_dir_ok": data_dir.exists() and data_dir.is_dir(),
            "backup_dir_ok": backup_dir.exists() and backup_dir.is_dir(),
            "log_dir_ok": log_dir.exists() and log_dir.is_dir(),
        },
        "performance": {
            "index_count": index_count,
            "sample_query_plan": " | ".join(plan_lines),
        },
    }


def _probe_dir_write(path: Path) -> dict:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "status": "OK", "message": "Ecriture disponible"}
    except Exception as exc:
        return {"ok": False, "status": "Erreur", "message": str(exc)}


async def _probe_db_write() -> dict:
    try:
        await execute_db_async(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """,
            ("diagnostic_last_write", datetime.now().isoformat(timespec="seconds")),
        )
        return {"ok": True, "status": "OK", "message": "Ecriture base disponible"}
    except Exception as exc:
        _rollback_current_db()
        return {"ok": False, "status": "Erreur", "message": str(exc)}


def _rollback_current_db() -> None:
    try:
        get_db().rollback()
    except Exception:
        pass


async def export_diagnostic_report() -> str:
    status = await get_system_status()
    return json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True)


def log_server_start() -> None:
    conn = connect_database(DATABASE_URL)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS system_logs (id SERIAL PRIMARY KEY, level TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO system_logs (level, message, created_at) VALUES (%s, %s, CURRENT_TIMESTAMP)",
            ("info", "Demarrage du serveur"),
        )
        conn.commit()
    finally:
        conn.close()
    write_text_log("system.log", "INFO | Demarrage du serveur")
