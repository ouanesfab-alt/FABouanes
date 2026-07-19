from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.core.config import APP_DATA_DIR, DATABASE_URL
from app.core.db_helpers import connect_database, postgres_pool_status
from app.core.activity import write_text_log
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import async_compat
from app.core.storage import LOCAL_BACKUP_DIR, LOG_DIR, get_pending_backup_marker, list_restore_backups
from app.version import VERSION_LABEL


def _ok_status(ok: bool) -> str:
    return "OK" if ok else "Attention"


@async_compat
async def get_system_status(db: AsyncSession | None = None) -> dict:
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_system_status_impl(session)
    return await _get_system_status_impl(db)


async def _get_system_status_impl(db: AsyncSession) -> dict:
    db_ok = False
    db_message = ""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        db_message = "Connexion base disponible"
    except Exception as exc:
        db_message = str(exc)

    backups = list_restore_backups()

    latest_job = None
    try:
        latest_job_res = await db.execute(text("SELECT * FROM backup_jobs ORDER BY id DESC LIMIT 1"))
        latest_job_row = latest_job_res.first()
        latest_job = dict(latest_job_row._mapping) if latest_job_row else None
    except Exception:
        pass

    index_count = 0
    plan_lines: list[str] = []
    try:
        index_row_res = await db.execute(
            text("SELECT COUNT(*) AS c FROM pg_indexes WHERE schemaname = current_schema() AND indexname LIKE 'idx_%'")
        )
        index_row = index_row_res.first()
        index_count = int(index_row.c if index_row else 0)

        # explain query plan: we can execute it via text explain on the session!
        query_plan_res = await db.execute(text("EXPLAIN SELECT id, name FROM clients ORDER BY name LIMIT 50"))
        for row in query_plan_res.all():
            row_dict = dict(row._mapping)
            detail = row_dict.get("detail") or row_dict.get("plan") or next(iter(row_dict.values()), "") or str(row)
            plan_lines.append(str(detail))
    except Exception:
        pass

    pending_marker = get_pending_backup_marker()
    data_dir = Path(APP_DATA_DIR)
    backup_dir = Path(LOCAL_BACKUP_DIR)
    log_dir = Path(LOG_DIR)
    latest_backup_file = next(iter(sorted(backup_dir.glob("*.sql"), reverse=True)), None) if backup_dir.exists() else None
    from app.services.backup_service import BACKGROUND_STATE
    write_status = await _probe_db_write(db)
    backup_write_status = _probe_dir_write(backup_dir)
    reconciliation = await reconcile_client_balances(db)

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
        "reconciliation": reconciliation,
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


async def _probe_db_write(db: AsyncSession) -> dict:
    try:
        await db.execute(
            text("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:key, :value, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """),
            {"key": "diagnostic_last_write", "value": datetime.now().isoformat(timespec="seconds")},
        )
        await db.commit()
        return {"ok": True, "status": "OK", "message": "Ecriture base disponible"}
    except Exception as exc:
        return {"ok": False, "status": "Erreur", "message": str(exc)}


async def reconcile_client_balances(db: AsyncSession) -> dict:
    import logging
    logger = logging.getLogger("fabouanes.system")
    stmt = text("""
        WITH calculated AS (
            SELECT c.id,
                   c.name,
                   c.opening_credit,
                   c.opening_credit
                     + COALESCE(s_finished.total, 0)
                     + COALESCE(s_raw.total, 0)
                     - COALESCE(p_versement.total, 0)
                     + COALESCE(p_avance.total, 0) AS calculated_balance
            FROM clients c
            LEFT JOIN (SELECT client_id, SUM(total) AS total FROM sales WHERE sale_type='credit' GROUP BY client_id) s_finished ON s_finished.client_id = c.id
            LEFT JOIN (SELECT client_id, SUM(total) AS total FROM raw_sales WHERE sale_type='credit' GROUP BY client_id) s_raw ON s_raw.client_id = c.id
            LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='versement' GROUP BY client_id) p_versement ON p_versement.client_id = c.id
            LEFT JOIN (SELECT client_id, SUM(amount) AS total FROM payments WHERE payment_type='avance' GROUP BY client_id) p_avance ON p_avance.client_id = c.id
        ),
        view_state AS (
            SELECT id, name, current_balance FROM clients_with_stats
        ),
        mv_state AS (
            SELECT client_id, name, balance FROM mv_client_balances
        )
        SELECT COALESCE(cal.id, vs.id, ms.client_id) AS id,
               COALESCE(cal.name, vs.name, ms.name) AS name,
               COALESCE(cal.calculated_balance, 0) AS calculated_balance,
               COALESCE(vs.current_balance, 0) AS view_balance,
               COALESCE(ms.balance, 0) AS mv_balance
        FROM calculated cal
        FULL JOIN view_state vs ON vs.id = cal.id
        FULL JOIN mv_state ms ON ms.client_id = COALESCE(cal.id, vs.id)
        WHERE ABS(COALESCE(cal.calculated_balance, 0) - COALESCE(vs.current_balance, 0)) > 0.01
           OR ABS(COALESCE(cal.calculated_balance, 0) - COALESCE(ms.balance, 0)) > 0.01
    """)
    try:
        res = await db.execute(stmt)
        rows = res.fetchall()
        discrepancies = []
        for row in rows:
            discrepancies.append({
                "client_id": int(row[0]) if row[0] is not None else 0,
                "name": str(row[1]) if row[1] is not None else "Inconnu",
                "calculated": float(row[2]),
                "view": float(row[3]),
                "materialized_view": float(row[4])
            })

        # Self-healing refresh if discrepancies in mv exist
        if any(abs(d["calculated"] - d["materialized_view"]) > 0.01 for d in discrepancies):
            try:
                await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_client_balances"))
                await db.commit()
                # Re-run reconciliation query
                res = await db.execute(stmt)
                rows = res.fetchall()
                discrepancies = []
                for row in rows:
                    discrepancies.append({
                        "client_id": int(row[0]) if row[0] is not None else 0,
                        "name": str(row[1]) if row[1] is not None else "Inconnu",
                        "calculated": float(row[2]),
                        "view": float(row[3]),
                        "materialized_view": float(row[4])
                    })
            except Exception as inner_exc:
                logger.warning("Could not refresh mv_client_balances during reconciliation check: %s", inner_exc)

        status_label = "Conforme" if not discrepancies else "Ecart detecte"
        return {
            "ok": not discrepancies,
            "status": status_label,
            "count": len(discrepancies),
            "discrepancies": discrepancies
        }
    except Exception as exc:
        logger.error("Error executing financial reconciliation: %s", exc)
        return {
            "ok": False,
            "status": "Erreur de verification",
            "count": 0,
            "discrepancies": [],
            "error": str(exc)
        }



@async_compat
async def export_diagnostic_report(db: AsyncSession | None = None) -> str:
    status = await get_system_status(db=db)
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
