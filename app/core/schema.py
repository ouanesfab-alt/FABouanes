from __future__ import annotations

import os
import secrets
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import APP_DATA_DIR, BASE_DIR, DATABASE_URL, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from app.core.storage import DB_PATH, ensure_runtime_dirs
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
    if getattr(conn, "dialect", "sqlite") == "postgres":
        row = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?",
            (table,),
        ).fetchone()
        return row is not None
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
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
        value = _scalar(conn, "SELECT value FROM app_settings WHERE key = ?", (key,))
        return str(value or "")
    except Exception:
        return ""


def _set_setting(conn, key: str, value: str) -> None:
    if not _has_table(conn, "app_settings"):
        return
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (key, value),
    )


def _rebuild_fts_if_needed(conn, table_name: str, expected_count_sql: str, insert_sql: str, *, force: bool = False) -> None:
    expected = int(_scalar(conn, expected_count_sql) or 0)
    current = int(_scalar(conn, f"SELECT COUNT(*) FROM {table_name}") or 0)
    if not force and current == expected:
        return
    conn.execute(f"DELETE FROM {table_name}")
    conn.execute(insert_sql)


def _ensure_sqlite_runtime_objects(conn) -> None:
    if getattr(conn, "dialect", "sqlite") != "sqlite":
        return
    try:
        fts_version = "2"
        rebuild_fts = _setting(conn, "sqlite_fts_runtime_version") != fts_version
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS clients_fts USING fts5(name, phone, address)")
        conn.execute("CREATE TRIGGER IF NOT EXISTS clients_fts_insert AFTER INSERT ON clients BEGIN INSERT INTO clients_fts(rowid, name, phone, address) VALUES (new.id, new.name, COALESCE(new.phone,''), COALESCE(new.address,'')); END")
        conn.execute("CREATE TRIGGER IF NOT EXISTS clients_fts_delete AFTER DELETE ON clients BEGIN DELETE FROM clients_fts WHERE rowid = old.id; END")
        conn.execute("CREATE TRIGGER IF NOT EXISTS clients_fts_update AFTER UPDATE ON clients BEGIN DELETE FROM clients_fts WHERE rowid = old.id; INSERT INTO clients_fts(rowid, name, phone, address) VALUES (new.id, new.name, COALESCE(new.phone,''), COALESCE(new.address,'')); END")
        _rebuild_fts_if_needed(
            conn,
            "clients_fts",
            "SELECT COUNT(*) FROM clients",
            "INSERT INTO clients_fts(rowid, name, phone, address) SELECT id, name, COALESCE(phone,''), COALESCE(address,'') FROM clients",
            force=rebuild_fts,
        )
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS sales_fts USING fts5(row_key UNINDEXED, client_name, item_name, item_kind, sale_date UNINDEXED)")
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS sales_fts_insert AFTER INSERT ON sales BEGIN
                INSERT INTO sales_fts(row_key, client_name, item_name, item_kind, sale_date)
                SELECT 'finished:' || new.id, COALESCE((SELECT name FROM clients WHERE id = new.client_id), 'Comptoir'),
                       (SELECT name FROM finished_products WHERE id = new.finished_product_id), 'produit final', new.sale_date;
            END;
            CREATE TRIGGER IF NOT EXISTS sales_fts_delete AFTER DELETE ON sales BEGIN
                DELETE FROM sales_fts WHERE row_key = 'finished:' || old.id;
            END;
            CREATE TRIGGER IF NOT EXISTS sales_fts_update AFTER UPDATE ON sales BEGIN
                DELETE FROM sales_fts WHERE row_key = 'finished:' || old.id;
                INSERT INTO sales_fts(row_key, client_name, item_name, item_kind, sale_date)
                SELECT 'finished:' || new.id, COALESCE((SELECT name FROM clients WHERE id = new.client_id), 'Comptoir'),
                       (SELECT name FROM finished_products WHERE id = new.finished_product_id), 'produit final', new.sale_date;
            END;
            CREATE TRIGGER IF NOT EXISTS raw_sales_fts_insert AFTER INSERT ON raw_sales BEGIN
                INSERT INTO sales_fts(row_key, client_name, item_name, item_kind, sale_date)
                SELECT 'raw:' || new.id, COALESCE((SELECT name FROM clients WHERE id = new.client_id), 'Comptoir'),
                       COALESCE(NULLIF(new.custom_item_name, ''), (SELECT name FROM raw_materials WHERE id = new.raw_material_id)),
                       'matiere premiere', new.sale_date;
            END;
            CREATE TRIGGER IF NOT EXISTS raw_sales_fts_delete AFTER DELETE ON raw_sales BEGIN
                DELETE FROM sales_fts WHERE row_key = 'raw:' || old.id;
            END;
            CREATE TRIGGER IF NOT EXISTS raw_sales_fts_update AFTER UPDATE ON raw_sales BEGIN
                DELETE FROM sales_fts WHERE row_key = 'raw:' || old.id;
                INSERT INTO sales_fts(row_key, client_name, item_name, item_kind, sale_date)
                SELECT 'raw:' || new.id, COALESCE((SELECT name FROM clients WHERE id = new.client_id), 'Comptoir'),
                       COALESCE(NULLIF(new.custom_item_name, ''), (SELECT name FROM raw_materials WHERE id = new.raw_material_id)),
                       'matiere premiere', new.sale_date;
            END;
            """
        )
        _rebuild_fts_if_needed(
            conn,
            "sales_fts",
            "SELECT (SELECT COUNT(*) FROM sales) + (SELECT COUNT(*) FROM raw_sales)",
            """
            INSERT INTO sales_fts(row_key, client_name, item_name, item_kind, sale_date)
            SELECT 'finished:' || s.id, COALESCE(c.name, 'Comptoir'), f.name, 'produit final', s.sale_date
            FROM sales s
            LEFT JOIN clients c ON c.id = s.client_id
            JOIN finished_products f ON f.id = s.finished_product_id
            UNION ALL
            SELECT 'raw:' || rs.id, COALESCE(c.name, 'Comptoir'), COALESCE(NULLIF(rs.custom_item_name, ''), r.name), 'matiere premiere', rs.sale_date
            FROM raw_sales rs
            LEFT JOIN clients c ON c.id = rs.client_id
            JOIN raw_materials r ON r.id = rs.raw_material_id
            """,
            force=rebuild_fts,
        )
        _set_setting(conn, "sqlite_fts_runtime_version", fts_version)
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS purchases_validate_bi BEFORE INSERT ON purchases
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0
            BEGIN SELECT RAISE(ABORT, 'achat invalide'); END;
            CREATE TRIGGER IF NOT EXISTS purchases_validate_bu BEFORE UPDATE ON purchases
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0
            BEGIN SELECT RAISE(ABORT, 'achat invalide'); END;
            CREATE TRIGGER IF NOT EXISTS sales_validate_bi BEFORE INSERT ON sales
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0 OR NEW.amount_paid < 0 OR NEW.balance_due < 0 OR NEW.sale_type NOT IN ('cash','credit')
            BEGIN SELECT RAISE(ABORT, 'vente invalide'); END;
            CREATE TRIGGER IF NOT EXISTS sales_validate_bu BEFORE UPDATE ON sales
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0 OR NEW.amount_paid < 0 OR NEW.balance_due < 0 OR NEW.sale_type NOT IN ('cash','credit')
            BEGIN SELECT RAISE(ABORT, 'vente invalide'); END;
            CREATE TRIGGER IF NOT EXISTS raw_sales_validate_bi BEFORE INSERT ON raw_sales
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0 OR NEW.amount_paid < 0 OR NEW.balance_due < 0 OR NEW.sale_type NOT IN ('cash','credit')
            BEGIN SELECT RAISE(ABORT, 'vente matiere invalide'); END;
            CREATE TRIGGER IF NOT EXISTS raw_sales_validate_bu BEFORE UPDATE ON raw_sales
            WHEN NEW.quantity <= 0 OR NEW.unit_price < 0 OR NEW.total < 0 OR NEW.amount_paid < 0 OR NEW.balance_due < 0 OR NEW.sale_type NOT IN ('cash','credit')
            BEGIN SELECT RAISE(ABORT, 'vente matiere invalide'); END;
            CREATE TRIGGER IF NOT EXISTS payments_validate_bi BEFORE INSERT ON payments
            WHEN NEW.amount <= 0 OR NEW.payment_type NOT IN ('versement','avance')
            BEGIN SELECT RAISE(ABORT, 'paiement invalide'); END;
            CREATE TRIGGER IF NOT EXISTS payments_validate_bu BEFORE UPDATE ON payments
            WHEN NEW.amount <= 0 OR NEW.payment_type NOT IN ('versement','avance')
            BEGIN SELECT RAISE(ABORT, 'paiement invalide'); END;
            CREATE TRIGGER IF NOT EXISTS stock_movements_validate_bi BEFORE INSERT ON stock_movements
            WHEN NEW.quantity < 0 OR NEW.direction NOT IN ('in','out','adjust')
            BEGIN SELECT RAISE(ABORT, 'mouvement stock invalide'); END;
            """
        )
    except Exception:
        pass


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
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )


def _seed_default_admin(conn) -> None:
    admin = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,)).fetchone()
    if not admin:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
            VALUES (?, ?, 'admin', 1, 1, CURRENT_TIMESTAMP)
            """,
            (DEFAULT_ADMIN_USERNAME, generate_password_hash(initial_admin_password())),
        )
        return
    try:
        insecure_hash = check_password_hash(str(admin["password_hash"]), "1234")
    except Exception:
        insecure_hash = False
    if insecure_hash and os.environ.get("FAB_ALLOW_INSECURE_DEFAULT_ADMIN", "0").strip() != "1":
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1, last_password_change_at = CURRENT_TIMESTAMP WHERE id = ?",
            (generate_password_hash(initial_admin_password()), int(admin["id"])),
        )


def _seed_other_operation(conn) -> None:
    row = conn.execute(
        "SELECT id FROM raw_materials WHERE lower(trim(name)) = lower(trim(?)) ORDER BY id LIMIT 1",
        (OTHER_OPERATION_NAME,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE raw_materials SET name = ?, unit = ? WHERE id = ?",
            (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT, int(row["id"])),
        )
        return
    conn.execute(
        """
        INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty)
        VALUES (?, ?, 0, 0, 0, 0, 0)
        """,
        (OTHER_OPERATION_NAME, OTHER_OPERATION_UNIT),
    )


def migrate_db(conn) -> None:
    _ensure_sqlite_runtime_objects(conn)
    conn.commit()



def init_db() -> None:
    ensure_runtime_dirs()
    conn = connect_database(DATABASE_URL, DB_PATH)
    try:
        migrate_db(conn)
        _seed_default_admin(conn)
        _seed_default_settings(conn)
        _seed_other_operation(conn)
        conn.commit()
    finally:
        conn.close()
