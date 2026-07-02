from __future__ import annotations

import os
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import APP_DATA_DIR, BASE_DIR, DATABASE_URL, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from app.core.storage import ensure_runtime_dirs
from app.core.db import connect_database, list_columns

MIGRATIONS_DIR = BASE_DIR / "migrations"
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


def _has_table(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn, table: str) -> set[str]:
    if not _has_table(conn, table):
        return set()
    return set(list_columns(conn, table))


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    if _has_table(conn, table) and column not in _table_columns(conn, table):
        conn.execute(ddl)



def _scalar(conn, query: str, params: tuple = ()):
    cur = conn.execute(query, params)
    try:
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()


def _setting(conn, key: str) -> str:
    if not _has_table(conn, "app_settings"):
        return ""
    try:
        value = _scalar(conn, "SELECT value FROM app_settings WHERE key = %s", (key,))
        return str(value or "")
    except Exception:
        return ""


def _set_setting(conn, key: str, value: str) -> None:
    if not _has_table(conn, "app_settings"):
        return
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (key, value),
    )


def _rebuild_fts_if_needed(conn, table_name: str, expected_count_sql: str, insert_sql: str, *, force: bool = False) -> None:
    from app.core.db_helpers import validate_identifier
    validate_identifier(table_name)
    expected = int(_scalar(conn, expected_count_sql) or 0)
    current = int(_scalar(conn, f"SELECT COUNT(*) FROM {table_name}") or 0)
    if not force and current == expected:
        return
    conn.execute(f"DELETE FROM {table_name}")
    conn.execute(insert_sql)





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


def migrate_db(conn) -> None:
    conn.commit()



def init_db() -> None:
    ensure_runtime_dirs()
    conn = connect_database(DATABASE_URL)
    try:
        migrate_db(conn)
        _seed_default_admin(conn)
        _seed_default_settings(conn)
        _seed_other_operation(conn)
        conn.commit()
    finally:
        conn.close()
