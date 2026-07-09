"""
Responsibility: Seed functions, configuration parameters, and backward-compatible init_db interface for schema.
"""
from __future__ import annotations

import os
import secrets
from werkzeug.security import generate_password_hash

from app.core.config import APP_DATA_DIR, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from app.core.storage import ensure_runtime_dirs

FIRST_ADMIN_PASSWORD_FILE = APP_DATA_DIR / "first_admin_password.txt"
OTHER_OPERATION_NAME = "AUTRE"
OTHER_OPERATION_UNIT = "unite"


def initial_admin_password() -> str:
    configured = str(DEFAULT_ADMIN_PASSWORD or "").strip()
    allow_insecure = os.environ.get("FAB_ALLOW_INSECURE_DEFAULT_ADMIN", "0").strip() == "1"
    if configured and (configured != "1234" or allow_insecure):
        return configured
    if FIRST_ADMIN_PASSWORD_FILE.exists():
        try:
            for line in FIRST_ADMIN_PASSWORD_FILE.read_text(encoding="utf-8").splitlines():
                if line.startswith("PIN="):
                    value = line.split("=", 1)[1].strip()
                    if value:
                        return value
        except Exception:
            pass
    pin = f"{secrets.randbelow(10000):04d}"
    if pin == "1234":
        pin = "9237"
    ensure_runtime_dirs()
    FIRST_ADMIN_PASSWORD_FILE.write_text(
        f"Utilisateur={DEFAULT_ADMIN_USERNAME}\nPIN={pin}\nChange ce PIN au premier login.\n",
        encoding="utf-8",
    )
    return pin


def _seed_default_settings(conn) -> None:
    defaults = (
        ("gdrive_backup_dir", ""),
        ("backup_snapshot_time", "02:00"),
        ("backup_local_retention", "30"),
        ("backup_event_retention", "100"),
        ("backup_last_nightly_date", ""),
    )
    for key, value in defaults:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )


def _seed_default_admin(conn) -> None:
    from app.core.config import settings
    if str(DEFAULT_ADMIN_PASSWORD or "").strip().lower() == "admin" and settings.env == "production" and not settings.desktop_mode:
        raise RuntimeError(
            "DEFAULT_ADMIN_PASSWORD cannot be 'admin' in production server mode. Set a strong password in your .env file."
        )
    admin = conn.execute("SELECT id, password_hash FROM users WHERE username = %s", (DEFAULT_ADMIN_USERNAME,)).fetchone()
    if not admin:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
            VALUES (%s, %s, 'admin', FALSE, TRUE, CURRENT_TIMESTAMP)
            """,
            (DEFAULT_ADMIN_USERNAME, generate_password_hash(initial_admin_password())),
        )


def _seed_other_operation(conn) -> None:
    row = conn.execute(
        "SELECT id FROM raw_materials WHERE lower(trim(name)) = lower(trim(%s)) ORDER BY id LIMIT 1",
        (OTHER_OPERATION_NAME,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE raw_materials SET name = %s, unit = %s WHERE id = %s",
            (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT, int(row["id"])),
        )
        return
    conn.execute(
        """
        INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty)
        VALUES (%s, %s, 0, 0, 0, 0, 0)
        """,
        (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT),
    )


def init_db() -> None:
    """Delegates to schema bootstrap."""
    from app.core.schema_bootstrap import bootstrap_schema
    bootstrap_schema()
