#!/usr/bin/env python3
"""Populate optional demo data without overriding existing user records."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fabouanes.config import APP_DATA_DIR, DATABASE_URL
from fabouanes.db import connect_database
from fabouanes.postgres_support import SQLITE_IMPORT_FILE_NAME
from fabouanes.runtime_app import init_db

SQLITE_IMPORT_PATH_HINT = APP_DATA_DIR / SQLITE_IMPORT_FILE_NAME


def _table_count(conn, table: str) -> int:
    cur = conn.execute(f"SELECT COUNT(*) AS c FROM {table}")
    row = cur.fetchone()
    cur.close()
    return int((row["c"] if row else 0) or 0)


def _ensure_row(conn, query: str, params: tuple, check_query: str, check_params: tuple) -> bool:
    cur = conn.execute(check_query, check_params)
    found = cur.fetchone()
    cur.close()
    if found:
        return False
    cur = conn.execute(query, params)
    cur.close()
    return True


def seed_demo() -> int:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is missing in .env")
        return 1

    init_db()
    conn = connect_database(DATABASE_URL, SQLITE_IMPORT_PATH_HINT)
    created = 0
    try:
        if _table_count(conn, "suppliers") == 0:
            created += int(
                _ensure_row(
                    conn,
                    "INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?)",
                    ("Fournisseur Demo", "0550 00 00 01", "Zone industrielle", "Donnees de demonstration"),
                    "SELECT id FROM suppliers WHERE lower(name) = lower(?) LIMIT 1",
                    ("Fournisseur Demo",),
                )
            )

        if _table_count(conn, "clients") == 0:
            created += int(
                _ensure_row(
                    conn,
                    "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (?, ?, ?, ?, ?)",
                    ("Client Demo", "0550 00 00 02", "Ville", "Donnees de demonstration", 0),
                    "SELECT id FROM clients WHERE lower(name) = lower(?) LIMIT 1",
                    ("Client Demo",),
                )
            )

        created += int(
            _ensure_row(
                conn,
                """
                INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("Mais Demo", "kg", 500, 35, 45, 50, 50),
                "SELECT id FROM raw_materials WHERE lower(name) = lower(?) LIMIT 1",
                ("Mais Demo",),
            )
        )

        created += int(
            _ensure_row(
                conn,
                """
                INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("Aliment Demo", "kg", 250, 95, 70),
                "SELECT id FROM finished_products WHERE lower(name) = lower(?) LIMIT 1",
                ("Aliment Demo",),
            )
        )

        conn.commit()
    except Exception as exc:  # pragma: no cover - explicit runtime diagnostics
        conn.rollback()
        print(f"ERROR: demo seed failed: {exc}")
        return 1
    finally:
        conn.close()

    print(f"OK: demo seed completed, created/updated records: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(seed_demo())
