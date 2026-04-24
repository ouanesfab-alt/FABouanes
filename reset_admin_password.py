#!/usr/bin/env python3
"""Reset or recreate admin credentials for local support use."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fabouanes.config import APP_DATA_DIR, DATABASE_URL
from fabouanes.db import connect_database
from fabouanes.postgres_support import SQLITE_IMPORT_FILE_NAME

SQLITE_IMPORT_PATH_HINT = APP_DATA_DIR / SQLITE_IMPORT_FILE_NAME


def reset_admin_password(username: str = "admin", new_password: str = "0000") -> bool:
    try:
        if not DATABASE_URL:
            print("ERROR: DATABASE_URL is missing in .env")
            return False

        conn = connect_database(DATABASE_URL, SQLITE_IMPORT_PATH_HINT)
        try:
            password_hash = generate_password_hash(new_password)
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing:
                cur = conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, must_change_password = 0, is_active = 1, role = 'admin'
                    WHERE username = ?
                    """,
                    (password_hash, username),
                )
                cur.close()
                action = "updated"
            else:
                cur = conn.execute(
                    """
                    INSERT INTO users (username, password_hash, role, must_change_password, is_active, last_password_change_at)
                    VALUES (?, ?, 'admin', 0, 1, CURRENT_TIMESTAMP)
                    """,
                    (username, password_hash),
                )
                cur.close()
                action = "created"

            conn.commit()
            print(f"OK: admin user {action}")
            print(f"USERNAME: {username}")
            print(f"PASSWORD: {new_password}")
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f"ERROR: failed to reset credentials: {exc}")
        return False


if __name__ == "__main__":
    pwd = (sys.argv[1] if len(sys.argv) > 1 else "0000").strip() or "0000"
    user = (sys.argv[2] if len(sys.argv) > 2 else "admin").strip() or "admin"
    ok = reset_admin_password(username=user, new_password=pwd)
    sys.exit(0 if ok else 1)
