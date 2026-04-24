from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fabouanes.db import connect_database, list_columns

POSTGRES_BACKUP_FORMAT = "fabouanes-postgres-backup-v1"
POSTGRES_BACKUP_SUFFIX = ".json"
POSTGRES_IMPORT_GUARD_TABLES: tuple[str, ...] = (
    "users",
    "clients",
    "suppliers",
    "raw_materials",
    "finished_products",
    "purchases",
    "production_batches",
    "sales",
    "raw_sales",
    "payments",
    "imported_client_history",
)
POSTGRES_TABLE_ORDER: tuple[str, ...] = (
    "users",
    "clients",
    "suppliers",
    "raw_materials",
    "finished_products",
    "purchase_documents",
    "sale_documents",
    "purchases",
    "production_batches",
    "production_batch_items",
    "saved_recipes",
    "saved_recipe_items",
    "sales",
    "raw_sales",
    "payments",
    "app_settings",
    "activity_logs",
    "error_logs",
    "system_logs",
    "audit_logs",
    "backup_jobs",
    "backup_runs",
    "api_refresh_tokens",
    "imported_client_history",
    "schema_migrations",
)
POSTGRES_ID_TABLES = tuple(table for table in POSTGRES_TABLE_ORDER if table != "app_settings")
SQLITE_IMPORT_FILE_NAME = "database.db"
SQLITE_IMPORT_METADATA_RULES = (
    ("sqlite_source_path", "sqlite_import_source_path"),
    ("sqlite_imported_at", "sqlite_imported_at"),
)


def _json_default(value: Any):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Type not serializable: {type(value)!r}")


def _row_to_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {column: row[column] for column in columns}
    return {column: row[index] for index, column in enumerate(columns)}


def _ordered_table_columns(conn, table: str) -> list[str]:
    cur = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return [row["column_name"] for row in rows]


def _target_has_data(conn) -> bool:
    for table in POSTGRES_IMPORT_GUARD_TABLES:
        cur = conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
        row = cur.fetchone()
        cur.close()
        if row is not None:
            return True
    return False


def _sqlite_has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _sqlite_looks_usable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with closing(sqlite3.connect(str(path))) as conn:
            return _sqlite_has_table(conn, "users")
    except sqlite3.Error:
        return False


def _sqlite_import_candidates(app_data_dir: Path, base_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    explicit = Path(app_data_dir) / SQLITE_IMPORT_FILE_NAME
    bundled = Path(base_dir) / SQLITE_IMPORT_FILE_NAME
    for candidate in (explicit, bundled):
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def detect_sqlite_import_source(app_data_dir: Path, base_dir: Path) -> Path | None:
    for candidate in _sqlite_import_candidates(app_data_dir, base_dir):
        if _sqlite_looks_usable(candidate):
            return candidate
    return None


def _insert_mapping(conn, table: str, payload: dict[str, Any]) -> None:
    if not payload:
        return
    columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    cur = conn.execute(
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
        tuple(payload[column] for column in columns),
    )
    cur.close()


def reset_postgres_sequences(conn) -> None:
    for table in POSTGRES_ID_TABLES:
        if "id" not in set(list_columns(conn, table)):
            continue
        cur = conn.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                EXISTS(SELECT 1 FROM {table})
            )
            """
        )
        cur.close()


def migrate_sqlite_import_metadata(conn) -> None:
    for suffix, target_key in SQLITE_IMPORT_METADATA_RULES:
        rows_cur = conn.execute(
            "SELECT key, value FROM app_settings WHERE key = ? OR key LIKE ?",
            (target_key, f"%{suffix}"),
        )
        rows = rows_cur.fetchall()
        rows_cur.close()
        target_row = next((row for row in rows if row["key"] == target_key), None)
        source_row = target_row or next((row for row in rows if row["key"] != target_key), None)

        if source_row and not target_row:
            upsert_cur = conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                (target_key, source_row["value"]),
            )
            upsert_cur.close()

        for row in rows:
            if row["key"] == target_key:
                continue
            delete_cur = conn.execute("DELETE FROM app_settings WHERE key = ?", (row["key"],))
            delete_cur.close()


def import_sqlite_into_postgres(conn, *, app_data_dir: Path, base_dir: Path) -> Path | None:
    if _target_has_data(conn):
        return None

    source_path = detect_sqlite_import_source(app_data_dir, base_dir)
    if source_path is None:
        return None

    with closing(sqlite3.connect(str(source_path))) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        try:
            for table in POSTGRES_TABLE_ORDER:
                if not _sqlite_has_table(sqlite_conn, table):
                    continue
                target_columns = set(list_columns(conn, table))
                rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
                for row in rows:
                    payload = {key: row[key] for key in row.keys() if key in target_columns}
                    _insert_mapping(conn, table, payload)

            reset_postgres_sequences(conn)
            cur = conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                ("sqlite_import_source_path", str(source_path)),
            )
            cur.close()
            cur = conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                ("sqlite_imported_at", datetime.now().isoformat(timespec="seconds")),
            )
            cur.close()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return source_path


def create_postgres_backup(database_url: str, db_path_hint: str | Path, target: Path) -> None:
    conn = connect_database(database_url, db_path_hint)
    try:
        tables: dict[str, list[dict[str, Any]]] = {}
        for table in POSTGRES_TABLE_ORDER:
            columns = _ordered_table_columns(conn, table)
            if not columns:
                tables[table] = []
                continue
            order_clause = " ORDER BY id" if "id" in columns else ""
            cur = conn.execute(f"SELECT {', '.join(columns)} FROM {table}{order_clause}")
            rows = cur.fetchall()
            cur.close()
            tables[table] = [_row_to_dict(row, columns) for row in rows]

        payload = {
            "format": POSTGRES_BACKUP_FORMAT,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "tables": tables,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    finally:
        conn.close()


def restore_postgres_backup(database_url: str, db_path_hint: str | Path, backup_path: str | Path) -> None:
    path = Path(backup_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Le fichier de sauvegarde PostgreSQL est invalide.") from exc

    if payload.get("format") != POSTGRES_BACKUP_FORMAT:
        raise RuntimeError("Format de sauvegarde PostgreSQL non pris en charge.")

    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, dict):
        raise RuntimeError("Le contenu de la sauvegarde est incomplet.")

    conn = connect_database(database_url, db_path_hint)
    try:
        cur = conn.execute(
            "TRUNCATE TABLE " + ", ".join(POSTGRES_TABLE_ORDER) + " RESTART IDENTITY CASCADE"
        )
        cur.close()
        for table in POSTGRES_TABLE_ORDER:
            rows = tables_payload.get(table, [])
            if not isinstance(rows, list):
                raise RuntimeError(f"Sauvegarde invalide pour la table {table}.")
            target_columns = set(list_columns(conn, table))
            for row in rows:
                if not isinstance(row, dict):
                    raise RuntimeError(f"Ligne de sauvegarde invalide pour la table {table}.")
                payload_row = {key: row[key] for key in row.keys() if key in target_columns}
                _insert_mapping(conn, table, payload_row)
        reset_postgres_sequences(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
