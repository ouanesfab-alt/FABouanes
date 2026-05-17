from __future__ import annotations

from pathlib import Path
from time import monotonic

from app.core.config import DATABASE_URL
from app.core.audit import audit_event
from app.core.db_access import get_db, query_db
from app.core.storage import DB_PATH


def database_size_info() -> dict:
    db_path = Path(DB_PATH)
    wal_path = Path(f"{db_path}-wal")
    shm_path = Path(f"{db_path}-shm")
    return {
        "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "shm_bytes": shm_path.stat().st_size if shm_path.exists() else 0,
        "db_path": str(db_path),
    }


def run_sqlite_maintenance() -> dict:
    started = monotonic()
    if DATABASE_URL.lower().startswith("postgres"):
        return {"ok": False, "message": "Maintenance SQLite indisponible avec PostgreSQL.", "details": database_size_info()}

    db = get_db()
    integrity = "unknown"
    try:
        row = query_db("PRAGMA integrity_check", (), one=True)
        if row is not None:
            integrity = str(row[0] if not hasattr(row, "keys") else row[0])
        db.execute("PRAGMA analysis_limit = 1000").close()
        db.execute("ANALYZE").close()
        db.execute("PRAGMA optimize").close()
        db.execute("PRAGMA wal_checkpoint(PASSIVE)").close()
        db.commit()
    except Exception as exc:
        audit_event("sqlite_maintenance", "system", "sqlite", status="failure", meta={"error": str(exc)})
        return {"ok": False, "message": f"Maintenance echouee: {exc}", "details": database_size_info(), "integrity": integrity}

    elapsed_ms = round((monotonic() - started) * 1000.0, 2)
    details = database_size_info()
    details["elapsed_ms"] = elapsed_ms
    audit_event("sqlite_maintenance", "system", "sqlite", after={"integrity": integrity, **details})
    return {
        "ok": integrity.lower() == "ok",
        "message": f"Maintenance terminee en {elapsed_ms} ms. Integrity: {integrity}",
        "integrity": integrity,
        "details": details,
    }
